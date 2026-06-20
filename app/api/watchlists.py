"""
Watchlist routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistSymbol
from app.schemas.watchlist import WatchlistCreate, WatchlistOut, AddSymbolRequest

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


@router.get("/", response_model=List[WatchlistOut])
def list_watchlists(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Watchlist).filter(Watchlist.user_id == current_user.id).all()


@router.post("/", response_model=WatchlistOut)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wl = Watchlist(user_id=current_user.id, name=payload.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


@router.post("/{watchlist_id}/symbols")
def add_symbol(watchlist_id: int, payload: AddSymbolRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    sym = WatchlistSymbol(watchlist_id=watchlist_id, symbol=payload.symbol, exchange=payload.exchange)
    db.add(sym)
    db.commit()
    return {"detail": "Symbol added"}


@router.delete("/{watchlist_id}/symbols/{symbol_id}")
def remove_symbol(watchlist_id: int, symbol_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sym = db.query(WatchlistSymbol).filter(
        WatchlistSymbol.id == symbol_id,
        WatchlistSymbol.watchlist_id == watchlist_id,
    ).first()
    if not sym:
        raise HTTPException(status_code=404, detail="Symbol not found")
    db.delete(sym)
    db.commit()
    return {"detail": "Symbol removed"}
