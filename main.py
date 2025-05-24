from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
import os
from pydantic import BaseModel
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
import asyncio
import csv
import io
import sys
import pandas as pd
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import ast

from dotenv import load_dotenv
load_dotenv()

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scanner_v1 import analyze_and_store  # Direct call to scan logic

app = FastAPI(title="PrivHawk Admin Panel", docs_url="/__sysadmin__/docs", redoc_url=None)

# Mount templates and static
BASE_DIR = Path(__file__).parent
app.mount("/__sysadmin__/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Session middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "dev-key"))

# MongoDB client
mongo: AsyncIOMotorClient | None = None
scheduler = AsyncIOScheduler()
DB_NAME = os.getenv("DB_NAME", "privacy_scan")

@app.on_event("startup")
async def startup():
    global mongo
    mongo = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    mongo.close()
    scheduler.shutdown()

# --- Auth placeholder (basic) ---
def get_current(_: Request):
    return "admin"

# --- Models ---
class URLIn(BaseModel):
    url: str
    account: str

class ScheduleIn(BaseModel):
    cron: str
    account: Optional[str] = "ALL"

# --- Utility to render template ---
def html(name, request, **ctx):
    ctx.update(request=request)
    ctx.setdefault("nav_links", [
        {"label": "Dashboard", "href": "/__sysadmin__/ui"},
        {"label": "URLs", "href": "/__sysadmin__/ui/urls"},
        {"label": "Schedules", "href": "/__sysadmin__/ui/schedules"},
        {"label": "Config", "href": "/__sysadmin__/ui/config"},
    ])
    return templates.TemplateResponse(name, ctx)

# --- Config Loader ---
def load_config_values(config_path):
    config_values = {}
    source = config_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            key = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            if key:
                try:
                    value = ast.literal_eval(node.value)
                    config_values[key] = value
                except Exception:
                    config_values[key] = "<Unparsable>"
    return config_values

# --- UI Pages ---
@app.get("/__sysadmin__/ui", response_class=HTMLResponse)
async def ui_home(request: Request, _: str = Depends(get_current)):
    return html("dashboard.html", request)

@app.get("/__sysadmin__/ui/urls", response_class=HTMLResponse)
async def ui_urls(request: Request, _: str = Depends(get_current)):
    return html("urls.html", request)

@app.get("/__sysadmin__/ui/schedules", response_class=HTMLResponse)
async def ui_schedules(request: Request, _: str = Depends(get_current)):
    return html("schedules.html", request)

@app.get("/__sysadmin__/ui/urls/table", response_class=HTMLResponse)
async def ui_url_table(request: Request):
    urls = await mongo[DB_NAME]["urls"].find({}).to_list(100)
    for u in urls:
        u["id"] = str(u["_id"])
    return templates.TemplateResponse("_url_table.html", {"request": request, "rows": urls})

@app.post("/__sysadmin__/urls/import")
async def import_urls_excel(file: UploadFile, request: Request):
    df = pd.read_excel(await file.read(), engine='openpyxl')
    for _, row in df.iterrows():
        await mongo[DB_NAME]["urls"].insert_one({
            "url": row["url"],
            "account": row["account"],
            "created_at": datetime.utcnow()
        })
    return await ui_url_table(request)

@app.post("/__sysadmin__/urls/edit")
async def edit_url_entry(request: Request):
    form = await request.form()
    url_id = form.get("id")
    new_url = form.get("url")
    new_account = form.get("account")
    await mongo[DB_NAME]["urls"].update_one({"_id": ObjectId(url_id)}, {"$set": {"url": new_url, "account": new_account}})
    return await ui_url_table(request)

@app.post("/__sysadmin__/urls")
async def add_url(request: Request, url: str = Form(...), account: str = Form(...)):
    await mongo[DB_NAME]["urls"].insert_one({"url": url, "account": account, "created_at": datetime.utcnow()})
    return await ui_url_table(request)

@app.post("/__sysadmin__/ui/config")
async def save_config_form(request: Request):
    form_data = await request.form()
    config_path = Path(__file__).resolve().parent.parent / "config.py"

    lines = []
    for key, val in form_data.items():
        try:
            parsed = ast.literal_eval(val)
            formatted = f"{key} = {repr(parsed)}\n"
        except Exception:
            formatted = f'{key} = "{val}"\n'
        lines.append(formatted)

    config_path.write_text("".join(lines), encoding="utf-8")
    return PlainTextResponse("✅ Config updated.")

@app.get("/__sysadmin__/ui/config", response_class=HTMLResponse)
async def config_editor(request: Request):
    config_path = Path(__file__).resolve().parent.parent / "config.py"
    config_values = load_config_values(config_path)

    return templates.TemplateResponse("config_form.html", {
        "request": request,
        "config": config_values,
        "nav_links": [
            {"label": "Dashboard", "href": "/__sysadmin__/ui"},
            {"label": "URLs", "href": "/__sysadmin__/ui/urls"},
            {"label": "Schedules", "href": "/__sysadmin__/ui/schedules"},
            {"label": "Config", "href": "/__sysadmin__/ui/config"},
        ]
    })




@app.post("/__sysadmin__/ui/config")
async def save_config_form(request: Request):
    form_data = await request.form()
    config_path = Path(__file__).resolve().parent.parent / "config.py"

    new_lines = []
    with config_path.open("r", encoding="utf-8") as f:
        existing_lines = f.readlines()

    for i, line in enumerate(existing_lines):
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in form_data:
                val = form_data[key]
                try:
                    parsed = json.loads(val)
                    new_lines.append(f"{key} = {json.dumps(parsed, indent=2)}\n")
                except Exception:
                    new_lines.append(f"{key} = \"{val}\"\n")
                form_data.pop(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Add any new keys
    for key, val in form_data.items():
        try:
            parsed = json.loads(val)
            new_lines.append(f"{key} = {json.dumps(parsed, indent=2)}\n")
        except Exception:
            new_lines.append(f"{key} = \"{val}\"\n")

    config_path.write_text("".join(new_lines), encoding="utf-8")
    return PlainTextResponse("✅ Config updated.")



@app.post("/__sysadmin__/ui/config")
async def save_config_form(request: Request):
    form_data = await request.form()
    config_path = Path(__file__).resolve().parent.parent / "config.py"

    lines = []
    for key, val in form_data.items():
        try:
            parsed = ast.literal_eval(val)
            formatted = f"{key} = {repr(parsed)}\n"
        except Exception:
            formatted = f'{key} = "{val}"\n'
        lines.append(formatted)

    config_path.write_text("".join(lines), encoding="utf-8")
    return PlainTextResponse("✅ Config updated.")

import ast

def load_config_values(config_path):
    config_values = {}
    source = config_path.read_text(encoding="utf-8")

    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            key = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            if key:
                try:
                    value = ast.literal_eval(node.value)
                    config_values[key] = value
                except Exception:
                    config_values[key] = "<Unparsable>"
    return config_values

# Add a scheduled scan
@app.post("/__sysadmin__/schedules")
async def add_schedule(request: Request, account: str = Form(...), url: str = Form(...), cron: str = Form(...)):
    job_id = f"{account}-{urlparse(url).netloc}"
    
    async def scan():
        await analyze_and_store(await async_playwright().start().chromium.launch(headless=True), url, urlparse(url).netloc, mongo[DB_NAME])

    scheduler.add_job(
        scan,
        CronTrigger.from_crontab(cron),
        id=job_id,
        name=account,
        replace_existing=True
    )
    return await sched_table(request)

# Return rendered schedule table
@app.get("/__sysadmin__/ui/schedules/table", response_class=HTMLResponse)
async def sched_table(request: Request):
    jobs = []
    for job in scheduler.get_jobs():
        cron = job.trigger.crontab if hasattr(job.trigger, 'crontab') else str(job.trigger)
        jobs.append({
            "id": job.id,
            "account": job.name,
            "url": job.args[0] if job.args else "—",
            "cron": cron,
            "next": job.next_run_time.strftime("%Y-%m-%d %H:%M") if job.next_run_time else "—"
        })
    return templates.TemplateResponse("_sched_table.html", {"request": request, "jobs": jobs})

# Delete a schedule
@app.delete("/__sysadmin__/schedules/{job_id}")
async def delete_schedule(job_id: str, request: Request):
    scheduler.remove_job(job_id)
    return await sched_table(request)
