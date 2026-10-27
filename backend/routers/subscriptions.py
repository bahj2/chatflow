from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

import billing as B
import payments as P
from core import db, current_user, superadmin, platform_settings

router = APIRouter(prefix="/api")


class CheckoutIn(BaseModel):
    item: str


class PlanIn(BaseModel):
    plan: Literal["starter", "pro", "business"]
    days: int = Field(30, ge=1, le=366)


@router.get("/public/plans")
async def public_plans():
    return {"plans": [{"key": k, **B.PLANS[k]} for k in B.PAID], "trial": B.PLANS["trial"], "topup": B.TOPUP}


@router.get("/billing")
async def billing(user=Depends(current_user)):
    bid = user["business_id"]
    invs = await db.invoices.find({"business_id": bid}, {"_id": 0}).sort("created_at", -1).to_list(20)
    ps = await platform_settings()
    return {"sub": await B.sub_status(db, bid), "plans": [{"key": k, **B.PLANS[k]} for k in B.PAID], "topup": B.TOPUP,
            "payments_ready": bool(ps and P.enabled(ps)), "auto_confirm": B.auto_confirm(ps), "invoices": [B.inv_view(i) for i in invs]}


@router.post("/billing/checkout")
async def billing_checkout(body: CheckoutIn, user=Depends(current_user)):
    return await B.checkout(db, user["business_id"], body.item, await platform_settings())


@router.get("/billing/invoices/{iid}")
async def billing_invoice(iid: str, user=Depends(current_user)):
    inv = await db.invoices.find_one({"id": iid, "business_id": user["business_id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return {**B.inv_view(inv), "sub": await B.sub_status(db, user["business_id"])}


@router.get("/billing/invoices/{iid}/qr.png")
async def billing_invoice_qr(iid: str):
    # Public by unguessable invoice id so <img> can load it; the QR only pays the platform's own account.
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0, "qr": 1})
    if not inv or not inv.get("qr"):
        raise HTTPException(404, "Not found")
    return Response(await P.qr_png(inv["qr"]), media_type="image/png", headers={"Cache-Control": "private, max-age=900"})


@router.get("/admin/invoices")
async def admin_invoices(status: str = "pending", user=Depends(superadmin)):
    flt = {} if status == "all" else {"status": status}
    invs = await db.invoices.find(flt, {"_id": 0}).sort("created_at", -1).to_list(300)
    names = {b["id"]: b["name"] async for b in db.businesses.find({"id": {"$in": [i["business_id"] for i in invs]}}, {"_id": 0, "id": 1, "name": 1})}
    return [{**B.inv_view(i), "business_id": i["business_id"], "business_name": names.get(i["business_id"])} for i in invs]


@router.post("/admin/invoices/{iid}/confirm")
async def admin_confirm(iid: str, user=Depends(superadmin)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv["status"] == "paid":
        raise HTTPException(409, "Already paid")
    await B.settle(db, inv, f"admin:{user['email']}")
    return {**B.inv_view(await db.invoices.find_one({"id": iid}, {"_id": 0})), "sub": await B.sub_status(db, inv["business_id"])}


@router.post("/admin/businesses/{bid}/plan")
async def admin_set_plan(bid: str, body: PlanIn, user=Depends(superadmin)):
    if not await db.businesses.find_one({"id": bid}, {"_id": 1}):
        raise HTTPException(404, "Business not found")
    if (await B.sub_status(db, bid))["exempt"]:
        raise HTTPException(400, "The platform account is never billed.")
    await B.activate(db, bid, body.plan, body.days, f"admin:{user['email']}")
    return await B.sub_status(db, bid)
