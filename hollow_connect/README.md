# HOLLOW-CONNECT — Team integration

This adds emergency reporting, personnel requests through categorized reports, coordinator assignment/dispatch, report tracking, and announcements to the existing Flet + SQL Server application.

## Installation
1. **Back up the SQL Server database**. Run `setup_connect.sql` in the same database as `database.py` (`ResidentInfors` by default). The script only creates new tables and seeds demonstration teams.
2. Copy `connect_engine.py` and `connect_screen.py` into the directory containing your team's `database.py`, `theme.py`, and `ui.py`.
3. In `screens/home.py`, add `import connect_screen` near its imports.
4. Add a tile where your other home tiles are constructed:

```python
ui.make_tile(
    ft.Icons.CAMPAIGN_OUTLINED,
    "COMMUNICATION",
    lambda e: connect_screen.show(
        page, user_id, level,
        on_back=lambda: show(page, user_id, level, name, on_logout)
    ),
)
```

**Important:** `show(page, user_id, level, name, on_logout)` is an illustrative home-screen signature based on the existing `main(1).py` call; adjust it to your real `screens/home.py`. That file wasn't provided, so this integration cannot be fully wired automatically. If the home module imports `make_tile` directly from `ui`, use that rather than `ui.make_tile`.

5. Run the original app (`main(1).py`); do not run `connect_screen.py` directly.
6. Login as a resident to report an emergency. Login as `admin` to acknowledge, assign, dispatch and resolve it.

## Behavior and limits
- The coordinator's **admin** ID is a demo-only permission check; production requires a proper role/permission table.
- A report is not a dispatch: statuses are Submitted → Acknowledged → Assigned → Dispatched → Resolved, or Cancelled before dispatch.
- Available teams are ranked by floor distance *within their specialty*. No route accessibility, actual travel time, or personnel availability beyond the team table is verified.
- SQL Server updates and history writes use a transaction. Team assignment locks report/team rows to reduce double booking.
- The module does **not** auto-create alerts in `alert_engine.py` or dispatch physical teams. Integrate those later once the team decides how notifications and simulated personnel work.
- No real emergency services are contacted. For a real emergency, call local emergency services; this is fictional hackathon software.
- Uses the existing account ID and floor; report descriptions are visible to the admin, so avoid entering real personal or medical data.

## Testing
Run `python -m unittest test_connect -v` from the package directory (requires your team's `database.py` with `pyodbc` installed). Tests cover pure validation and demo role checks, not live SQL Server or Flet behavior.
