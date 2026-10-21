"""Seeds a business's Notion knowledge through the real sync code using a mocked Notion API (no real workspace needed)."""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

import notion_kb as N

T = lambda s: [{"plain_text": s}]
PAGES = [
    {"id": "page-shop", "object": "page", "url": "https://notion.so/page-shop", "last_edited_time": "2026-06-01T10:00:00.000Z",
     "parent": {"type": "workspace"}, "properties": {"title": {"type": "title", "title": T("Shop info & policies")}}},
    {"id": "page-delivery", "object": "page", "url": "https://notion.so/page-delivery", "last_edited_time": "2026-06-01T09:00:00.000Z",
     "parent": {"type": "page_id"}, "properties": {"title": {"type": "title", "title": T("Delivery")}}},
]
ROWS = [
    {"id": "row-1", "object": "page", "url": "https://notion.so/row-1", "last_edited_time": "2026-06-01T08:00:00.000Z", "parent": {"type": "data_source_id"},
     "properties": {"Name": {"type": "title", "title": T("Iced Palm Sugar Latte")}, "Price": {"type": "number", "number": 2.75},
                    "Size": {"type": "select", "select": {"name": "Large"}}, "In stock": {"type": "checkbox", "checkbox": True}}},
    {"id": "row-2", "object": "page", "url": "https://notion.so/row-2", "last_edited_time": "2026-06-01T08:00:00.000Z", "parent": {"type": "data_source_id"},
     "properties": {"Name": {"type": "title", "title": T("Durian Smoothie")}, "Price": {"type": "number", "number": 3.5},
                    "Size": {"type": "select", "select": {"name": "Regular"}}, "In stock": {"type": "checkbox", "checkbox": False}}},
]
BLOCKS = {
    "page-shop": [
        {"id": "b1", "type": "heading_2", "heading_2": {"rich_text": T("Opening hours")}, "has_children": False},
        {"id": "b2", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": T("Mon–Sat 7:00–21:00")}, "has_children": False},
        {"id": "b3", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": T("Sunday 8:00–12:00 only (morning)")}, "has_children": False},
        {"id": "b4", "type": "toggle", "toggle": {"rich_text": T("Refund policy")}, "has_children": True},
        {"id": "b5", "type": "table", "table": {}, "has_children": True},
        {"id": "b6", "type": "child_page", "child_page": {"title": "Delivery"}, "has_children": True},
    ],
    "b4": [{"id": "b41", "type": "paragraph", "paragraph": {"rich_text": T("Refunds within 24 hours with the receipt. Wifi password: palmtree2026")}, "has_children": False}],
    "b5": [{"id": "b51", "type": "table_row", "table_row": {"cells": [T("Branch"), T("Address")]}, "has_children": False},
           {"id": "b52", "type": "table_row", "table_row": {"cells": [T("Riverside"), T("#12 Sisowath Quay, Phnom Penh")]}, "has_children": False}],
    "page-delivery": [{"id": "d1", "type": "paragraph", "paragraph": {"rich_text": T("Free delivery over $10 inside Phnom Penh via Grab or Nham24.")}, "has_children": False}],
}
CALLS = []


def handler(req: httpx.Request) -> httpx.Response:
    path = req.url.path.replace("/v1", "", 1)
    CALLS.append(f"{req.method} {path}")
    assert req.headers["Notion-Version"] == N.VERSION and req.headers["Authorization"] == "Bearer ntn_mocktoken123456"
    if path == "/users/me":
        return httpx.Response(200, json={"object": "user", "name": "ReplyFlow", "type": "bot", "bot": {"workspace_name": "Sunrise Coffee"}})
    if path == "/search":
        body = json.loads(req.content)
        if body["filter"]["value"] == "page":
            if body.get("start_cursor") == "c2":
                return httpx.Response(200, json={"results": PAGES[1:], "has_more": False})
            return httpx.Response(200, json={"results": PAGES[:1], "has_more": True, "next_cursor": "c2"})
        return httpx.Response(200, json={"results": [{"id": "ds-1", "object": "data_source", "title": T("Price list")}], "has_more": False})
    if path == "/data_sources/ds-1/query":
        return httpx.Response(200, json={"results": ROWS, "has_more": False})
    if path.startswith("/blocks/"):
        return httpx.Response(200, json={"results": BLOCKS.get(path.split("/")[2], []), "has_more": False})
    return httpx.Response(404, json={"code": "object_not_found", "message": "nope"})


async def main(email: str):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    bid = user["business_id"]
    N.TRANSPORT = httpx.MockTransport(handler)
    me = await N.whoami("ntn_mocktoken123456")
    await db.notion_docs.delete_many({"business_id": bid})
    await db.notion_links.update_one({"business_id": bid}, {"$set": {
        "business_id": bid, "token_enc": N.seal("ntn_mocktoken123456"), "hint": "3456", "bot_name": me["name"],
        "workspace": me["bot"]["workspace_name"], "connected_at": N.now_iso(), "status": "queued", "last_error": "", "knowledge": ""}}, upsert=True)
    await N.sync_business(db, bid)
    first = len(CALLS)
    CALLS.clear()
    await N.sync_business(db, bid)
    link = await db.notion_links.find_one({"business_id": bid}, {"_id": 0, "token_enc": 0})
    print("status:", link["status"], "| pages:", link["page_count"], "| chars:", link["chars"], "| error:", link["last_error"])
    print("api calls first sync:", first, "| second (cached) sync:", len(CALLS), CALLS)
    print("----- knowledge -----\n" + link["knowledge"])


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "admin@replyflow.com"))
