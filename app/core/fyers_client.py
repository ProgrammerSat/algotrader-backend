"""
Fyers API v3 client wrapper.
Manages the singleton fyers session after OAuth login.
"""
from fyers_apiv3 import fyersModel
from app.core.config import get_settings

settings = get_settings()

# Singleton holder for the authenticated fyers client
_fyers_client = None


def get_fyers_client() -> fyersModel.FyersModel | None:
    return _fyers_client


def set_fyers_client(access_token: str) -> fyersModel.FyersModel:
    global _fyers_client
    _fyers_client = fyersModel.FyersModel(
        client_id=settings.fyers_app_id,
        token=access_token,
        log_path="",
        is_async=False,
    )
    return _fyers_client


def build_auth_url() -> str:
    """Generate the Fyers OAuth authorization URL."""
    session = fyersModel.SessionModel(
        client_id=settings.fyers_app_id,
        secret_key=settings.fyers_secret_key,
        redirect_uri=settings.fyers_redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    return session.generate_authcode()


def exchange_code_for_token(auth_code: str) -> str:
    """Exchange the Fyers auth_code for an access_token."""
    session = fyersModel.SessionModel(
        client_id=settings.fyers_app_id,
        secret_key=settings.fyers_secret_key,
        redirect_uri=settings.fyers_redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    session.set_token(auth_code)
    response = session.generate_token()
    if response.get("s") != "ok":
        raise ValueError(f"Token exchange failed: {response}")
    return response["access_token"]
