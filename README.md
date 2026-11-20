# HOLLOW-MED integration for Hollow City (SQL Server + Flet)

This is **not** the previous SQLite `hollow_med.py`: your teammate's new app uses `database.get_connection()` with pyodbc, SQL Server `ResidentInfors`, and string `Account.UserID` mapped to `Residents.ID` through `Account.ResidentID`.

## Install

1. **Back up** your existing SQL Server database. Run `setup_hollow_med.sql` against `ResidentInfors` using SQL Server Management Studio / Azure Data Studio. It creates only `Med_*` tables; existing teammate tables are unchanged.
2. Place `hollow_med_sql.py` and `medical_screen.py` in the **same folder as `database.py` and `main.py`**. Do not replace `database.py`, `hollow_sim.py`, or `alert_engine.py`.
3. The uploaded `main(1).py` imports `screens.login` and `screens.home`, but those two files were **not uploaded**. To add the medical page, edit your teammate's `screens/home.py` where the MEDICAL tile is defined. Import `medical_screen` and change its click callback to call:

```python
medical_screen.show(page, user_id, level,
                    on_back=lambda: show(page, user_id, level, name, go_login))
```

This assumes `screens/home.py` exports `show(page, user_id, level, name, go_login)` as invoked in your teammate's main. If its local names differ, adjust the callback. The screen does not edit the home page automatically.

4. Install the team's dependencies (`flet`, `pyodbc`) and configure the SQL Server ODBC driver/connection. Your teammate uses `Trusted_Connection=yes`, which may require Windows integrated authentication; on macOS, this **will not automatically work** without an appropriate SQL Server authentication setup. Ask your teammate for their connection method; do not hard-code credentials into the project.
5. Start the teammate's existing main app. The `medical_screen` will show a resident's level conditions, appointment requests, medical assistance requests, and notices.

## Backend examples

```python
import hollow_med_sql as med
print(med.level_overview(3))
print(med.forecast(3, 300))
print(med.clinics())
print(med.suggest_support(3, 'medical_kits', 20))
print(med.resident_dashboard('A0000001'))  # use an actual existing account
```

## Important limitations

- **Not a clinical system.** Health score thresholds and forecasts are fictional and are not medical advice.
- The new clinic inventories and capacity values are **demo seeds**, not measurements of real stock.
- Appointments are **requests**; there is no scheduled time, treatment duration, or confirmed reservation until a staff workflow is built.
- `suggest_support()` makes **read-only recommendations**; no automatic transfers or dispatches.
- Staff permissions, verified emergency dispatch, secure user sessions, and real-time UI updates are **not implemented**. The Flet screen must only be accessed through your existing authenticated app. Do not deploy publicly.
- The SQL Server schema of `Residents.Health`, `Residents.Level`, `Level_Effects`, `Levels`, and `Level_Systems` was inferred from the uploaded `hollow_sim.py` queries; the original SQL DDL was not supplied. Test against a backed-up copy and adjust if actual column types differ.
- Existing alert engine is independent. `Med_Notices` are separate stored medical announcements; no automatic alert-engine subscription is claimed.
- A one-million-resident forecast query can be expensive. Add an index on `Residents([Level],Health)` after testing query plans.
