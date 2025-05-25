from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import os

from dotenv import load_dotenv
load_dotenv()

print("LOADED AUTH:", __file__)

# ────────────────────────────────
# 1. Config & OAuth setup
# ────────────────────────────────
config = Config(".env")
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter()

# ────────────────────────────────
# 2. Login route
# ────────────────────────────────
@router.get("/login")
async def login(request: Request):
    # Use public hostname in production to avoid mismatches
    redirect_uri = "https://privhawk.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

# ────────────────────────────────
# 3. OAuth callback
# ────────────────────────────────
@router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)

    # Debug print
    print("FULL TOKEN FROM GOOGLE:", token)

    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=400,
            detail="Google token did not include id_token"
        )

    # Must pass a dict with the id_token only
    user = await oauth.google.parse_id_token(request, {"id_token": id_token})

    allowed = [e.strip().lower() for e in os.getenv("ALLOWED_USERS", "").split(",") if e.strip()]
    if allowed and user["email"].lower() not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    request.session["user"] = dict(user)
    return RedirectResponse(url="/__sysadmin__/ui")

# ────────────────────────────────
# 4. Logout
# ────────────────────────────────
@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")
