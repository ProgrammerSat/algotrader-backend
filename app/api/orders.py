"""
Orders routes: place, cancel, list orders.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.fyers_client import get_fyers_client
from app.deps import get_current_user
from app.models.user import User
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderOut

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/", response_model=List[OrderOut])
def list_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.placed_at.desc()).all()


@router.post("/", response_model=OrderOut)
def place_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = Order(user_id=current_user.id, **payload.model_dump())
    
    if not payload.is_paper:
        fyers = get_fyers_client()
        if not fyers:
            raise HTTPException(status_code=403, detail="Fyers not linked")
        fyers_payload = {
            "symbol": payload.symbol,
            "qty": payload.quantity,
            "type": 2 if payload.order_type == "MARKET" else 1,
            "side": 1 if payload.side == "BUY" else -1,
            "productType": payload.product_type,
            "limitPrice": payload.price,
            "stopPrice": payload.stop_price,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
        }
        response = fyers.place_order(fyers_payload)
        if response.get("s") != "ok":
            msg = response.get("message") or response.get("errmsg") or str(response)
            raise HTTPException(status_code=400, detail=f"Fyers error: {msg}")
        order.fyers_order_id = response.get("id")
        order.status = "PLACED"
    else:
        order.status = "PAPER_PLACED"

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.fyers_order_id and not order.is_paper:
        fyers = get_fyers_client()
        if fyers:
            fyers.cancel_order({"id": order.fyers_order_id})

    order.status = "CANCELLED"
    db.commit()
    return {"detail": "Order cancelled"}


@router.get("/live")
def get_live_orders(current_user: User = Depends(get_current_user)):
    """Fetch live orders from Fyers."""
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers not linked")
    return fyers.orderbook()


@router.get("/positions")
def get_positions(current_user: User = Depends(get_current_user)):
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers not linked")
    return fyers.positions()


@router.get("/holdings")
def get_holdings(current_user: User = Depends(get_current_user)):
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers not linked")
    return fyers.holdings()

