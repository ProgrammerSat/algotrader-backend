"""
Strategy CRUD routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.strategy import Strategy, StrategyStatus
from app.schemas.strategy import StrategyCreate, StrategyUpdate, StrategyOut

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("/", response_model=List[StrategyOut])
def list_strategies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Strategy).filter(Strategy.user_id == current_user.id).all()


@router.post("/", response_model=StrategyOut)
def create_strategy(
    payload: StrategyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    strategy = Strategy(user_id=current_user.id, **payload.model_dump())
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.user_id == current_user.id
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.patch("/{strategy_id}", response_model=StrategyOut)
def update_strategy(
    strategy_id: int,
    payload: StrategyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.user_id == current_user.id
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(strategy, field, value)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.user_id == current_user.id
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    db.delete(strategy)
    db.commit()
    return {"detail": "Strategy deleted"}


@router.post("/{strategy_id}/toggle")
def toggle_strategy(strategy_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.user_id == current_user.id
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strategy.status = (
        StrategyStatus.ACTIVE if strategy.status != StrategyStatus.ACTIVE else StrategyStatus.STOPPED
    )
    db.commit()
    db.refresh(strategy)
    return {"status": strategy.status}
