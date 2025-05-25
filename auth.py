from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
import os
from starlette.config import Config

# Load environment variables
config = Config(".env")
oauth = OAuth(config)

oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@app.get("/login")
async def login(request: Request):
    redirect_uri = "https://privhawk.com/auth/callback"  # Hardcoded to avoid IP redirect
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)

    # Avoid crash: gracefully handle missing id_token
    id_token = token.get("id_token")
    if not id_token:
        print("OAuth token response missing id_token:", token)
        raise HTTPException(status_code=400, detail="Google token did not include an id_token")

    # Safe to parse only now
    user = await oauth.google.parse_id_token(request, {"id_token": id_token})

    allowed = os.getenv("ALLOWED_USERS", "").split(",")
    if user["email"] not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    request.session["user"] = dict(user)
    return RedirectResponse(url="/__sysadmin__/ui")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")
