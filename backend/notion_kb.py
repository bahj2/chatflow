"""Read-only Notion knowledge sync: each business pastes its own internal integration secret."""
import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet

API = "https://api.notion.com/v1"
VERSION = "2026-03-11"
MAX_PAGES = 150
MAX_ROWS = 200
MAX_DEPTH = 4
PAGE_CHARS = 15000
TOTAL_CHARS = 30000
TRANSPORT = None  # tests may inject httpx.MockTransport

logger = logging.getLogger(__name__)
_fernet = Fernet(os.environ["NOTION_ENC_KEY"].encode())


def seal(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def unseal(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class NotionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def friendly(e: NotionError) -> str:
    if e.status == 401:
        return "Notion rejected this secret. Copy it again from notion.so/profile/integrations."
    if e.status == 403:
        return "The ReplyFlow connection can't read content. In Notion, open the integration → Capabilities → turn on “Read content”."
    if e.status == 404:
        return "A page is no longer shared with ReplyFlow. Share it again (••• → Connections)."
    if e.status == 429:
        return "Notion is busy right now. ReplyFlow will try again on the next sync."
    if e.status == 0:
        return "Could not reach Notion. Please try again in a minute."
    return f"Notion error: {e.message[:150]}"


class Client:
    def __init__(self, token: str):
        self.h = httpx.AsyncClient(base_url=API, timeout=30, transport=TRANSPORT,
                                   headers={"Authorization": f"Bearer {token}", "Notion-Version": VERSION, "Content-Type": "application/json"})
        self.last = 0.0

    async def close(self):
        await self.h.aclose()

    async def req(self, method: str, path: str, **kw) -> dict:
        for attempt in range(5):
            wait = 0.34 - (time.monotonic() - self.last)  # stay under 3 requests / second
            if wait > 0:
                await asyncio.sleep(wait)
            self.last = time.monotonic()
            try:
                r = await self.h.request(method, path, **kw)
            except httpx.HTTPError as e:
                if attempt == 4:
                    raise NotionError(0, "network", str(e))
                await asyncio.sleep(2)
                continue
            if r.status_code in (429, 500, 502, 503, 504, 529) and attempt < 4:
                try:
                    delay = min(int(r.headers.get("Retry-After", "2")), 30)
                except ValueError:
                    delay = 2
                await asyncio.sleep(delay + random.random())
                continue
            if r.status_code >= 400:
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                raise NotionError(r.status_code, body.get("code", ""), body.get("message", r.text[:200]))
            return r.json()
        raise NotionError(429, "rate_limited", "retry limit reached")

    async def paged(self, method: str, path: str, body: dict = None, limit: int = 10000) -> list:
        out, cursor = [], None
        while len(out) < limit:
            extra = {"start_cursor": cursor} if cursor else {}
            if method == "GET":
                data = await self.req("GET", path, params={"page_size": 100, **extra})
            else:
                data = await self.req("POST", path, json={**(body or {}), "page_size": 100, **extra})
            out += data.get("results", [])
            if not data.get("has_more") or not data.get("next_cursor"):
                break
            cursor = data["next_cursor"]
        return out[:limit]


def rt(arr) -> str:
    return "".join(x.get("plain_text", "") for x in arr or [])


PREFIX = {"paragraph": "", "heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ", "numbered_list_item": "- ",
          "to_do": "", "toggle": "", "quote": "> ", "callout": "", "code": ""}


def block_line(b: dict) -> str:
    t = b.get("type", "")
    o = b.get(t) or {}
    if t in PREFIX:
        txt = rt(o.get("rich_text"))
        if t == "to_do":
            txt = ("[x] " if o.get("checked") else "[ ] ") + txt
        return PREFIX[t] + txt if txt.strip() else ""
    if t == "table_row":
        return " | ".join(rt(c) for c in o.get("cells", []))
    if t == "child_page":
        return f"(sub-page: {o.get('title', '')})"
    if t == "child_database":
        return f"(table: {o.get('title', '')})"
    if t in ("bookmark", "embed", "link_preview"):
        return o.get("url", "")
    if t == "equation":
        return o.get("expression", "")
    if t in ("image", "file", "pdf", "video", "audio"):
        cap = rt(o.get("caption"))
        return f"[{t}] {cap}" if cap else ""
    return ""


async def page_text(c: Client, block_id: str, depth: int = 0, out: list = None) -> list:
    out = [] if out is None else out
    for b in await c.paged("GET", f"/blocks/{block_id}/children", limit=1000):
        if sum(len(x) for x in out) > PAGE_CHARS:
            break
        line = block_line(b)
        if line:
            out.append("  " * depth + line)
        if b.get("has_children") and depth < MAX_DEPTH and b.get("type") not in ("child_page", "child_database"):
            await page_text(c, b["id"], depth + 1, out)
    return out


def prop_val(p: dict) -> str:
    t = p.get("type")
    v = p.get(t)
    if t in ("title", "rich_text"):
        return rt(v)
    if t in ("select", "status"):
        return (v or {}).get("name", "")
    if t == "multi_select":
        return ", ".join(x.get("name", "") for x in v or [])
    if t in ("number", "url", "email", "phone_number"):
        return "" if v is None else str(v)
    if t == "checkbox":
        return "yes" if v else "no"
    if t == "date":
        return ((v or {}).get("start") or "") + (f" → {v['end']}" if v and v.get("end") else "")
    if t == "formula":
        f = v or {}
        val = f.get(f.get("type"))
        return "" if val is None else str(val)
    if t == "people":
        return ", ".join(x.get("name", "") for x in v or [] if x.get("name"))
    if t == "files":
        return ", ".join(x.get("name", "") for x in v or [])
    if t == "unique_id":
        return f"{(v or {}).get('prefix') or ''}{(v or {}).get('number', '')}"
    return ""


def page_title(p: dict) -> str:
    for prop in (p.get("properties") or {}).values():
        if prop.get("type") == "title":
            return rt(prop.get("title")).strip() or "Untitled"
    return "Untitled"


def is_row(p: dict) -> bool:
    return (p.get("parent") or {}).get("type") in ("data_source_id", "database_id")


def row_props(p: dict) -> str:
    lines = []
    for name, prop in (p.get("properties") or {}).items():
        if prop.get("type") == "title":
            continue
        val = prop_val(prop).strip()
        if val:
            lines.append(f"{name}: {val}")
    return "\n".join(lines)


async def whoami(token: str) -> dict:
    c = Client(token)
    try:
        return await c.req("GET", "/users/me")
    finally:
        await c.close()


async def fetch_docs(token: str, old: dict) -> list:
    c = Client(token)
    try:
        newest = {"sort": {"direction": "descending", "timestamp": "last_edited_time"}}
        pages = await c.paged("POST", "/search", {**newest, "filter": {"property": "object", "value": "page"}}, limit=MAX_PAGES)
        sources = await c.paged("POST", "/search", {"filter": {"property": "object", "value": "data_source"}}, limit=20)
        found, table_of = {p["id"]: p for p in pages if not p.get("in_trash")}, {}
        for ds in sources:
            for row in await c.paged("POST", f"/data_sources/{ds['id']}/query", {}, limit=MAX_ROWS):
                if not row.get("in_trash") and len(found) < MAX_PAGES + MAX_ROWS:
                    found.setdefault(row["id"], row)
                    table_of[row["id"]] = rt(ds.get("title")) or "Table"
        docs = []
        for p in found.values():
            prev = old.get(p["id"])
            if prev and prev.get("last_edited_time") == p.get("last_edited_time"):
                body = prev.get("body", "")
            else:
                body = "\n".join(await page_text(c, p["id"]))[:PAGE_CHARS]
            props = row_props(p) if is_row(p) else ""
            head = f"Table: {table_of[p['id']]}\n" if p["id"] in table_of else ""
            docs.append({"notion_id": p["id"], "title": page_title(p)[:200], "url": p.get("url", ""), "kind": "row" if is_row(p) else "page",
                         "last_edited_time": p.get("last_edited_time"), "body": body, "text": (head + "\n".join(x for x in (props, body) if x)).strip()})
        return docs
    finally:
        await c.close()


def build_knowledge(docs: list) -> tuple:
    parts, total, truncated = [], 0, False
    for d in docs:
        if not d["text"]:
            continue
        chunk = f"### {d['title']}\n{d['text']}\n"
        if total + len(chunk) > TOTAL_CHARS:
            truncated = True
            chunk = chunk[:max(0, TOTAL_CHARS - total)]
        if chunk:
            parts.append(chunk)
            total += len(chunk)
        if truncated:
            break
    return "\n".join(parts).strip(), truncated


async def sync_business(db, bid: str):
    stale = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    link = await db.notion_links.find_one_and_update(
        {"business_id": bid, "$or": [{"status": {"$ne": "syncing"}}, {"sync_started_at": {"$lt": stale}}]},
        {"$set": {"status": "syncing", "sync_started_at": now_iso()}})
    if not link:
        return
    try:
        old = {d["notion_id"]: d async for d in db.notion_docs.find({"business_id": bid}, {"_id": 0})}
        docs = await fetch_docs(unseal(link["token_enc"]), old)
        if not await db.notion_links.find_one({"business_id": bid, "token_enc": link["token_enc"]}, {"_id": 1}):
            return  # disconnected or replaced while syncing
        for d in docs:
            await db.notion_docs.update_one({"business_id": bid, "notion_id": d["notion_id"]},
                                            {"$set": {**d, "business_id": bid, "chars": len(d["text"]), "synced_at": now_iso()}}, upsert=True)
        await db.notion_docs.delete_many({"business_id": bid, "notion_id": {"$nin": [d["notion_id"] for d in docs]}})
        knowledge, truncated = build_knowledge(docs)
        await db.notion_links.update_one({"business_id": bid}, {"$set": {
            "status": "ok", "last_sync_at": now_iso(), "last_error": "", "page_count": len(docs),
            "knowledge": knowledge, "chars": len(knowledge), "truncated": truncated}})
    except NotionError as e:
        await db.notion_links.update_one({"business_id": bid}, {"$set": {"status": "invalid" if e.status == 401 else "error",
                                                                         "last_error": friendly(e), "last_attempt_at": now_iso()}})
    except Exception as e:
        logger.exception("notion sync failed for %s: %s", bid, e)
        await db.notion_links.update_one({"business_id": bid}, {"$set": {"status": "error", "last_error": "Sync failed. Please try again later.",
                                                                         "last_attempt_at": now_iso()}})


async def sync_all(db):
    bids = await db.notion_links.distinct("business_id", {"status": {"$ne": "invalid"}})
    sem = asyncio.Semaphore(5)

    async def one(bid):
        async with sem:
            await sync_business(db, bid)
    await asyncio.gather(*(one(b) for b in bids))
    logger.info("notion hourly sync done for %s businesses", len(bids))


async def knowledge(db, bid: str) -> str:
    doc = await db.notion_links.find_one({"business_id": bid}, {"_id": 0, "knowledge": 1})
    return (doc or {}).get("knowledge", "")
