"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base, SessionLocal
from app.core.fyers_client import set_fyers_client
from app.api import auth, market, strategies, orders, trades, watchlists, screener, ai_screener

# Create all DB tables
import app.models  # noqa — ensures models are registered with Base
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: restore the Fyers client from the DB so restarts don't break the link."""
    db = SessionLocal()
    try:
        from app.models.user import User
        # Find the most recently linked user with a stored token
        user = db.query(User).filter(
            User.fyers_linked == True,
            User.fyers_access_token != None,
        ).order_by(User.id.desc()).first()

        if user and user.fyers_access_token:
            try:
                set_fyers_client(user.fyers_access_token)
                print(f"✅ Fyers client restored for user: {user.email}")
            except Exception as e:
                print(f"⚠️  Could not restore Fyers client: {e}")
        else:
            print("ℹ️  No linked Fyers account found — connect via Dashboard.")
    finally:
        db.close()

    yield  # app runs here


app = FastAPI(
    title="AlgoTrader API",
    description="Algorithmic Trading Platform powered by Fyers API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(market.router)
app.include_router(strategies.router)
app.include_router(orders.router)
app.include_router(trades.router)
app.include_router(watchlists.router)
app.include_router(screener.router)
app.include_router(ai_screener.router)


@app.get("/")
def root():
    return {"message": "AlgoTrader API is running 🚀", "docs": "/docs"}


@app.get("/health")
def health():
    """Also returns whether Fyers is active."""
    from app.core.fyers_client import get_fyers_client
    return {
        "status": "ok",
        "fyers_client_active": get_fyers_client() is not None,
    }

