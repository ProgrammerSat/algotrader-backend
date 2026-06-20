"""
Trade log & P&L analytics routes.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.trade_log import TradeLog
from app.schemas.trade_log import TradeLogCreate, TradeLogOut

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("/", response_model=List[TradeLogOut])
def list_trades(
    strategy_id: Optional[int] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(TradeLog).filter(TradeLog.user_id == current_user.id)
    if strategy_id:
        q = q.filter(TradeLog.strategy_id == strategy_id)
    return q.order_by(TradeLog.entry_time.desc()).limit(limit).all()


@router.get("/summary")
def trade_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trades = db.query(TradeLog).filter(TradeLog.user_id == current_user.id).all()
    total = len(trades)
    if total == 0:
        return {"total_trades": 0, "total_pnl": 0, "win_rate": 0, "avg_pnl": 0}

    closed = [t for t in trades if t.exit_price is not None]
    winners = [t for t in closed if (t.pnl or 0) > 0]
    total_pnl = sum(t.pnl or 0 for t in closed)

    return {
        "total_trades": total,
        "closed_trades": len(closed),
        "open_trades": total - len(closed),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(len(winners) / len(closed) * 100, 2) if closed else 0,
        "avg_pnl": round(total_pnl / len(closed), 2) if closed else 0,
    }


@router.post("/", response_model=TradeLogOut)
def log_trade(
    payload: TradeLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = TradeLog(user_id=current_user.id, **payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
