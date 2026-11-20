# HOLLOW-SHELTER — Flet + SQL Server integration

This is a **fictional simulation**, not a real evacuation safety tool. Infrastructure status percentages are simulated scores. Never treat a recommendation as a verified route or order.

## What it does
- Classifies levels as normal, caution, unsafe, or unknown based on the team's `Level_Systems` scores.
- Displays reasons for an alert and potential temporary shelter destinations based on safe simulated levels and configured free capacity.
- Allows residents to request temporary relocation through their existing account ID.
- Stores pending requests; a staff coordinator must approve a specific destination and provide route/instruction text before the app displays an assignment.
- Prevents double-reserving shelter capacity on approved requests with SQL Server locks; staff can mark arrival to convert a reservation into occupied capacity.
- Does **not** automatically move people, issue evacuation orders, send alerts, or change the resident's registered home level.

## Installation
1. Back up the team's `ResidentInfors` SQL Server database. Run `setup_shelter.sql` on a **test copy** first. It creates three new tables and does not modify the original ones.
2. Put `shelter_engine.py` and `shelter_screen.py` beside the existing `database.py`, `theme.py`, and `main(1).py`.
3. In `screens/home.py` (not supplied with the shared files), import `shelter_screen` and add a tile callback:

```python
shelter_screen.show(page, user_id,
    on_back=lambda: show(page, user_id, level, name, go_login))
```

Your team's `main(1).py` calls `home.show(page, user_id, level, name, go_login)`. The tile can use `ui.make_tile(ft.Icons.HOME_OUTLINED, "SHELTER", lambda e: ...)`, depending on how the home screen is structured.
4. **Configure real shelter capacity** in the test database. All levels initially have zero available capacity intentionally. Example demo setup: `UPDATE dbo.Shelter_Capacity SET Capacity=200, Occupied=20 WHERE [Level]=5;` (adjust based on your fictional scenario).
5. Use the team's existing SQL Server credentials/ODBC driver configuration. On macOS, `Trusted_Connection=yes` may not work without additional setup.
6. Run the existing Flet app. For a demo, trigger a `housing_collapse` using your teammate's simulation and open HOLLOW-SHELTER on an affected account.

## Staff approval example (do NOT expose directly to residents)
```python
import shelter_engine as shelter
print(shelter.suggestions(3, party_size=4))
assignment_id = shelter.approve_request(
    request_id=1, destination_level=5,
    instructions="Report to the designated shelter coordinator. Use only the officially verified route.",
    coordinator_id="admin")
shelter.arrival_confirmed(assignment_id)
```
**Important:** Staff authorization is NOT implemented in these functions. Only call from an authenticated and authorized staff interface. `coordinator_id` is a record label, not proof of identity.

## Current limitations
- No actual floor plans, transport access checks, mobility requirements, household grouping validation, live alert subscription, or automated mass evacuation.
- The capacity table is separate from residential housing inventory; staff must populate capacity from verified simulation scenario values.
- The resident account-to-level mapping assumes `Account.[Level]` exists, as seen in `database.py`. The original database DDL was not uploaded.
- The team hasn't supplied `screens/home.py`, so the project cannot patch the existing home screen automatically.
- This prototype is **not fully tested against SQL Server or the installed Flet version**. Run tests with `python -m unittest -v test_shelter.py` and validate on a backed-up test database.
- Cancellation/departure workflows, transport routing, accessible housing constraints, and mass evacuation optimization are future work.
