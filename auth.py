from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import os
from authlib.common.security import generate_token


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
    nonce = generate_token()
    request.session["nonce"] = nonce
    redirect_uri = "https://privhawk.com/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri, nonce=nonce)

# ────────────────────────────────
# 3. OAuth callback
# ────────────────────────────────
@router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)

    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing id_token in token response")

    nonce = request.session.get("nonce")
    if not nonce:
        raise HTTPException(status_code=400, detail="Missing stored nonce for session")

    # validate token with nonce
    user = await oauth.google.parse_id_token(token, nonce=nonce)

    allowed = os.getenv("ALLOWED_USERS", "").split(",")
    if user["email"] not in allowed:
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
