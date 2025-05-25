from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
import os
from starlette.config import Config
from fastapi import APIRouter, Request, HTTPException   # ← add APIRouter here


# Load environment variables

# -----------------------------------------------------------------------------
# 0.  OAuth configuration
# -----------------------------------------------------------------------------
config = Config(".env")                # loads GOOGLE_CLIENT_ID / SECRET, etc.
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# -----------------------------------------------------------------------------
# 1.  Router
# -----------------------------------------------------------------------------
router = APIRouter()

# ----- LOGIN ---------------------------------------------------------------
@router.get("/login")
async def login(request: Request):
    # Hard-coded redirect (public hostname) avoids IP/port mismatch in prod
    redirect_uri = "https://privhawk.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

# ----- CALLBACK ------------------------------------------------------------
@router.get("/auth/callback")
async def auth_callback(request: Request):
    # Exchange the ‘code’ for tokens
    token = await oauth.google.authorize_access_token(request)

    # ── Defensive check ──
    id_token = token.get("id_token")
    if not id_token:
        print("OAuth token response missing id_token:", token)   # Debug only
        raise HTTPException(
            status_code=400,
            detail="Google token did not include an id_token",
        )

    # Verify & decode ID token  ❯❯  pass ONLY the id_token
    user = await oauth.google.parse_id_token(request, {"id_token": id_token})

    # ── Email allow-list ──
    allowed = [e.strip().lower() for e in os.getenv("ALLOWED_USERS", "").split(",") if e.strip()]
    if allowed and user["email"].lower() not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    # Store in session
    request.session["user"] = dict(user)
    return RedirectResponse(url="/__sysadmin__/ui")

# ----- LOGOUT --------------------------------------------------------------
@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")