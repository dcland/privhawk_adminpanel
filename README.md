# PrivHawk – Internal Sys-Admin Panel & Scanner

> **Purpose**
> This repository contains two independent pieces of tooling:
>
> 1. **`scanner_v1.py`** – Playwright-based website-privacy scanner.
> 2. **`admin_panel/`** – A tiny FastAPI application that lets internal staff run the scanner on demand, schedule periodic scans, and manage the URL list.
>
> **‼️  *For internal debugging only – do not expose publicly.***

---

## 1. Folder Structure

```
privhawk/
├── scanner_v1.py          # async crawler & scanner
├── detection_rules.py     # pluggable detectors (no circular imports)
├── detector_config.py     # DETECTION_RULES = [cls() ...]
├── ssl_utils.py           # helper to fetch certificate metadata
├── config.py              # all scanner constants (Mongo URI, proxy, flags…)
│
├── admin_panel/           # FastAPI “debug panel”
│   └── main.py
|   └── requirements.txt # **admin panel only**
│
├── requirements.txt       # everything (scanner + panel)

```

---

## 2. Quick Start

### 2.1 Clone & create venv

```bash
git clone <repo>
cd privhawk
python -m venv venv && source venv/bin/activate
```

### 2.2 Install (admin panel only)

```bash
pip install -r requirements.txt
```

> If you plan to run the **scanner** from the same venv, use `requirements.txt` instead (includes Playwright + BS4).

### 2.3 One-shot scan (CLI)

```bash
python scanner_v1.py https://www.etoro.com/es/ 0 --direct
```

### 2.4 Launch admin panel

```bash

export ADMIN_USER=admin
export ADMIN_PASS=changeme

uvicorn admin_panel.main:app --host 127.0.0.1 --port 9000 --reload
```

* Navigate to `http://127.0.0.1:9000/__sysadmin__/docs`
* Authenticate → you’ll see interactive Swagger UI.

---

## 3. Admin Panel Features

| Endpoint                                  | What it does                                                         |
| ----------------------------------------- | -------------------------------------------------------------------- |
| `POST /__sysadmin__/scan/run`             | Run scanner once on a single URL (or file) – returns subprocess PID. |
| `POST /__sysadmin__/urls`                 | Add a URL to the crawl list with an *account* (client) name.         |
| `GET  /__sysadmin__/urls`                 | List URLs (optionally filter by account).                            |
| `POST /__sysadmin__/urls/import`          | Upload Excel/CSV (first column = URLs) and assign to an account.     |
| `DELETE /__sysadmin__/urls/{id}`          | Remove a URL from DB.                                                |
| `POST /__sysadmin__/schedules`            | Add a cron-like job (APScheduler) that spawns scans on a schedule.   |
| `GET  /__sysadmin__/schedules`            | List active jobs (cron + next run).                                  |
| `DELETE /__sysadmin__/schedules/{job_id}` | Remove/disable a job.                                                |

*All routes live under `/__sysadmin__` to keep them out of sight.*

---

## 4. Configuration

Edit **`config.py`** to change:

* `MONGO_URI`, `DB_NAME`, …
* Proxy settings (`PROXY`)
* Scanner concurrency (`MAX_CONCURRENT_TASKS`)
* Keyword dictionaries & tracker lists.

If you change `config.py`, simply restart the scanner process or the admin panel.

---

## 5. Security Notes

* Basic HTTP auth only – good for an internal VPN / SSH-tunnel use-case.
* Bind Uvicorn to `127.0.0.1` or behind an authenticated reverse-proxy.
* **Do not** expose `/__sysadmin__` over the public internet.

---

## 6. Roadmap (discard when real UI arrives)

| Planned | Item                                                        |
| ------- | ----------------------------------------------------------- |
| ◻︎      | WebSocket live log stream for running scans                 |
| ◻︎      | Toggle scanner flags from the panel (depth, timeout)        |
| ◻︎      | UI polish (Tailwind/HTMX) – current HTML is functional only |
| ◻︎      | RBAC & audit logs if promoted beyond “temporary”            |

---

Made with ☕ & 🦘 by the PrivHawk team – *debug fast, scrap later* 🗑️.
