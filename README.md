# HOLLOW-EXPLORE — runnable surface exploration prototype

This is a **fictional simulation**, not a real-world expedition safety system. It is a working local web app built with **Python's standard library, SQLite, HTML, CSS, and JavaScript**. No `pip install` needed.

## Start in PyCharm / terminal

1. Unzip the project into one folder.
2. Open that folder in PyCharm or VS Code.
3. Run `python server.py` (or `python3 server.py`).
4. Visit **http://127.0.0.1:8765** in your browser.
5. Enter a resident ID (1–1000 in the initial demo) and click **Load profile**.
6. To test the full workflow, select a mission for a resident with a preferred occupation and health ≥65; approve the application in Command Center, start it, submit a report, then verify the report. The resident's `money` field increases exactly once.

The first launch creates `hollow_world.sqlite3` with **1,000 simulated residents**, using your teammate's `hollow_db.py` schema. Later launches reuse the same file and **do not erase your data**. The original team's database builder is destructive; do not run it on a database you need to keep.

## Features

- Fictional clickable surface map with seven sectors, hazard readings, confidence and resource clues.
- Three sample missions with pay, expected duration, preferred occupations and hazard thresholds.
- Volunteer applications, eligibility checks, coordinator approval/rejection.
- Equipment forecast (oxygen, battery, water) and return reserve check.
- Start mission, submit field report, coordinator verification and single-payment compensation.
- A live coordinator dashboard with outstanding applications, active explorers, unverified reports, total credits paid.
- SQLite storage using the existing `residents` table and `money` balance; separate `surface_*` and `exploration_*` tables.

## Tests

Run `python -m unittest -v test_explore.py`.

## Integrating with your team's app

`explore.py` contains the reusable logic. `server.py` exposes JSON endpoints including `/api/map`, `/api/missions`, `/api/resident?id=1`, `/api/equipment?hours=3&hazard=20`, `/api/apply`, `/api/decide`, `/api/start`, `/api/report`, and `/api/verify`.

To use the team's **existing** database, set environment variable `HOLLOW_DB` to its SQLite file path **before** starting `server.py`. The file must already contain the `residents` and `levels` tables. The exploration tables will be added without deleting existing tables. If your team's database only exists in memory, it must first be persisted to a file or the application must share the same live database connection through an integrated server.

## Important prototype limitations

- **No authentication or permissions.** The resident selector and coordinator controls are open to anyone who can access this local demo. Do **not** deploy it publicly. Implement secure sessions, authorization, request ownership checks, CSRF protection, and audit logging first.
- Sector coordinates are fictional 0–100 grid coordinates, **not real GPS**. No live geolocation, weather or sensor feeds.
- Equipment consumption, mission eligibility and compensation values are fictional assumptions, not medical or real-world safety guidance.
- Missions and sectors are seeded examples; edit `SECTORS` and `MISSIONS` in `explore.py` to change them. Existing seeded rows are preserved on restart.
- Mission start/finish are manually controlled; no actual location tracking, communication, sensor telemetry, rescue dispatch or physical resource deduction yet.
- Field reports improve confidence, but do not automatically declare an area safe. No route optimization or verified hazard classification yet.
- Reports and pay require coordinator verification; credits are issued to the existing `residents.money` field only once.
- For a million residents, use the team's existing persistent database instead of generating a million demo residents during a presentation.
