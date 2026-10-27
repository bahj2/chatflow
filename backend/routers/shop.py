import uuid
from typing import Optional, Literal

import jwt
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field

import media as M
import payments as P
from core import db, JWT_SECRET, JWT_ALG, now_iso, get_settings, current_user
from ai import load_products
from orders import settle_order, set_att_status

router = APIRouter(prefix="/api")


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=1000)
    image_media_id: str = ""

@router.get("/orders")
async def list_orders(status: Optional[Literal["pending", "paid", "expired", "cancelled"]] = None, user=Depends(current_user)):
    flt = {"business_id": user["business_id"], **({"status": status} if status else {})}
    return await db.orders.find(flt, {"_id": 0, "qr": 0, "md5": 0}).sort("created_at", -1).to_list(300)


async def own_order(oid: str, user: dict) -> dict:
    o = await db.orders.find_one({"id": oid, "business_id": user["business_id"]}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@router.post("/orders/{oid}/mark-paid")
async def order_mark_paid(oid: str, user=Depends(current_user)):
    o = await own_order(oid, user)
    if o["status"] == "paid":
        raise HTTPException(409, "This order is already paid")
    await settle_order(o, f"seller:{user['email']}")
    return await db.orders.find_one({"id": oid}, {"_id": 0, "qr": 0, "md5": 0})


@router.post("/orders/{oid}/cancel")
async def order_cancel(oid: str, user=Depends(current_user)):
    o = await own_order(oid, user)
    if o["status"] == "paid":
        raise HTTPException(409, "Paid orders can't be cancelled")
    await db.orders.update_one({"id": oid}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
    await set_att_status([oid], "cancelled")
    return await db.orders.find_one({"id": oid}, {"_id": 0, "qr": 0, "md5": 0})


@router.post("/payments/preview")
async def payments_preview(user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    if not P.enabled(s):
        raise HTTPException(400, "Add your Bakong account ID (or a KHQR.dev token) and press Save first")
    if s.khqr_token:
        ok, err = await P.token_ok(s.khqr_token)
        if not ok:
            raise HTTPException(400, f"KHQR.dev token problem: {err}")
    try:
        q = await P.make_qr(s, 1.0, "USD", "RF-TEST")
    except Exception as e:
        raise HTTPException(400, f"Could not create the QR: {e}")
    media = await M.save_media(db, user["business_id"], q["png"], "image/png", "khqr")
    return {"media_id": media["id"], "mode": q["mode"], "deeplink": q["deeplink"]}

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/media/{mid}")
async def get_media(mid: str, auth: Optional[str] = None):
    data, doc = await M.load_media(db, mid)
    if not data:
        raise HTTPException(404, "Not found")
    if doc["kind"] == "seller_voice":
        try:
            sub = jwt.decode(auth or "", JWT_SECRET, algorithms=[JWT_ALG])["sub"]
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Not authenticated")
        owner = await db.users.find_one({"id": sub}, {"_id": 0, "business_id": 1})
        if not owner or owner["business_id"] != doc["business_id"]:
            raise HTTPException(404, "Not found")
        return Response(data, media_type=doc["content_type"], headers={"Cache-Control": "private, no-store"})
    return Response(data, media_type=doc["content_type"], headers={"Cache-Control": "public, max-age=86400"})


@router.post("/media/image")
async def upload_image(file: UploadFile = File(...), user=Depends(current_user)):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(400, "Please upload a JPG, PNG or WEBP image")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 5 MB")
    doc = await M.save_media(db, user["business_id"], data, file.content_type, "product")
    return {"id": doc["id"]}


@router.get("/products")
async def list_products(user=Depends(current_user)):
    return await load_products(user["business_id"])


@router.post("/products")
async def create_product(body: ProductIn, user=Depends(current_user)):
    bid = user["business_id"]
    if await db.products.count_documents({"business_id": bid, "is_deleted": False}) >= 300:
        raise HTTPException(400, "Product limit reached (300)")
    doc = {"id": str(uuid.uuid4()), "business_id": bid, **body.model_dump(), "is_deleted": False, "created_at": now_iso()}
    await db.products.insert_one(dict(doc))
    return doc


@router.put("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user=Depends(current_user)):
    flt = {"id": pid, "business_id": user["business_id"], "is_deleted": False}
    if not (await db.products.update_one(flt, {"$set": body.model_dump()})).matched_count:
        raise HTTPException(404, "Product not found")
    return await db.products.find_one(flt, {"_id": 0})


@router.delete("/products/{pid}")
async def delete_product(pid: str, user=Depends(current_user)):
    res = await db.products.update_one({"id": pid, "business_id": user["business_id"], "is_deleted": False}, {"$set": {"is_deleted": True}})
    if not res.matched_count:
        raise HTTPException(404, "Product not found")
    return {"ok": True}
