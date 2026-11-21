# Hollow City

A desktop simulation of a 10-level underground city. Residents live, work and
get sick on their level; oxygen, power and other systems drain over time;
staff coordinate medical care, shelter relocation and surface expeditions.

> **Simulation only.** Scores, forecasts and procedures are fictional and are
> not medical, safety or emergency guidance.


## What it does

| Area | Description |
|---|---|
| **Login / Register** | Resident accounts; the ID letter is assigned from the chosen floor level (Level 1 = A, Level 2 = B, ...). |
| **Alert System** | Live light-battery and oxygen sensors with 70% / 50% info marks and Yellow / Orange / Red alerts. A banner appears on every screen; all alerts are kept in a notification list with an unread badge. |
| **Medical** | Health score, clinic appointment requests, assistance requests, a score-based forecast, and announcements. Staff can publish notices, view clinic inventory and get read-only support suggestions. |
| **Shelter** | Level status (normal / unsafe), relocation requests, and staff approval of destinations, arrivals and capacity. |
| **Explore** | Surface missions with eligibility checks, applications, reports and staff verification with rewards. |
| **Map** | Surface sector map with hazard zones, routes from the base and mission info. |
| **Survival Guide / Calendar** | Two standalone tkinter tools opened in their own windows. |
| **My Info** | Password-protected profile view and edit. |
| **Admin simulation** | Logging in as `admin` starts a city-wide simulation: per-level population, systems, workforce, crews in transit, events you can trigger, and a live log. |

## Tech stack

- Python 3.10+
- [Flet](https://flet.dev) (UI)
- SQL Server (Express is enough) via `pyodbc`
- tkinter (the two standalone tools)

## Requirements

- **Windows** (the app connects to SQL Server with Windows authentication)
- Python 3.10 or newer, added to PATH
- SQL Server (Express edition is fine) and SQL Server Management Studio (SSMS)
- Microsoft **ODBC Driver 17 or 18 for SQL Server**

## Setup

### 1. Create the database

In SSMS, open a new query and run:

```sql
CREATE DATABASE ResidentInfors;
```

### 2. Load the schema and data

Run these files **in this order**, each against the `ResidentInfors` database:

1. `sql/Sql_Script.sql` - tables, indexes, constraints and stored procedures
2. `sql/02_seed_small_tables.sql` - levels, systems, clinics, sectors, missions, etc.
3. `sql/03_seed_residents.sql` - creates the residents (2,000,000 for the full-scale simulation)

> Alternative: restore the full backup instead of steps 2-3 (SSMS: right-click
> **Databases** > **Restore Database** > **Device**). Backup link:
> `<link to .bak file>`. The database name must be `ResidentInfors`.

### 3. Run the app

Double-click `run.bat`, or from a terminal:

```bat
set HOLLOW_DB_SERVER=localhost\SQLEXPRESS
python -m pip install -r requirements.txt
python main.py
```

`HOLLOW_DB_SERVER` defaults to `localhost`. Use `localhost\SQLEXPRESS` for a
default SQL Server Express install. The database name can be changed with
`HOLLOW_DB_NAME` (default `ResidentInfors`).

On start, the app resets the simulation world to its initial state (every
resident alive, systems at 100%, event log cleared), so every launch begins
from the beginning. With 2,000,000 residents this can take a few seconds.

## Accounts

- **Staff / simulation:** user ID `admin`, password `<admin password>`
- **Resident:** register a new account in the app, or use `<test user ID>` /
  `<test password>`

Admin unlocks the city simulation, staff review tools in Shelter, Explore and
Medical, and the level forecast for any level.

## Project structure

```
main.py               App entry point
ui.py, theme.py       Shared Flet components and colors
banner.py             Alert banner shown above every screen
alert_engine.py       Background sensor simulation and notifications
hollow_sim.py         City-wide simulation (admin)
database.py           Connection, login, profile, account creation
hollow_med_sql.py     Medical logic
shelter_engine.py     Shelter logic
explore_sql.py        Explore (missions, reports, rewards) logic
tools_launcher.py     Opens the tkinter tools as separate processes
screens/              One module per screen
tools/                survival_guide.py, survival_calendar.py
sql/                  Database scripts
```

## Troubleshooting

| Message | Cause / fix |
|---|---|
| `No SQL Server ODBC driver installed` | Install ODBC Driver 17 or 18 for SQL Server. |
| `Login failed` / `Cannot open database "ResidentInfors"` | Wrong `HOLLOW_DB_SERVER`, the database does not exist, or your Windows account has no access. |
| `Invalid object name 'Explore_Sectors'` (or `Med_...`) | The schema script was not run on this database. |
| `AttributeError` on start | Different Flet version. Install the one in `requirements.txt`. |
| Simulation feels slow | SQL Server Express limits memory and CPU; 2,000,000 rows is heavy for it. |

## Known limitations

- Passwords are stored as plain text in `Account.Password` (demo project, do
  not reuse real passwords).
- Windows authentication only.
- Resident and simulation data are fictional.
