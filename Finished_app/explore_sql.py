"""HOLLOW-EXPLORE on SQL Server (ResidentInfors). Port of explore.py.
Run sql/04_explore.sql once before using. Simulation only.
Every action returns a message string, or raises ValueError (safe to show)."""
from contextlib import contextmanager
import pyodbc
import database

RESOURCES = ("none", "water", "food", "equipment", "other")
ADMIN_ID = "admin"   # same rule as shelter_engine / the rest of the app


def _require_admin(actor_id):
    """Staff-only guard, enforced here and not only in the UI."""
    if str(actor_id or "").strip().lower() != ADMIN_ID:
        raise ValueError("Staff access required")


@contextmanager
def _connect():
    con = database.get_connection()
    try:
        yield con
    finally:
        con.close()          # uncommitted work is rolled back


def _rows(cur, sql, *args):
    cur.execute(sql, *args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _resident(cur, user_id):
    row = cur.execute(
        "SELECT r.ID, r.Work, r.Health, r.Money "
        "FROM Account a JOIN Residents r ON r.ID = a.ResidentID "
        "WHERE a.UserID = ?", user_id).fetchone()
    if not row:
        raise ValueError("This account has no resident record")
    return dict(id=int(row[0]), work=(row[1] or "").lower(),
                health=row[2] or 0, money=row[3] or 0)


_MISSION_SQL = """
    SELECT m.MissionID id, m.Title title, m.SectorCode sector, s.Name sector_name,
           m.Kind kind, m.DurationHours hours, m.BaseReward reward,
           m.MaxHazard max_hazard, m.PreferredJobs jobs, m.Objective objective,
           m.[Status] status, s.Hazard hazard, s.[Status] sector_status
    FROM Explore_Missions m JOIN Explore_Sectors s ON s.Code = m.SectorCode"""


def equipment(hours, hazard=0):
    """Fictional planning numbers, same formula as explore.py."""
    oxygen = round(100 - hours * (9 + hazard * .04), 1)
    battery = round(100 - hours * (7 + hazard * .03), 1)
    water = round(100 - hours * 6, 1)
    return dict(oxygen=max(0, oxygen), battery=max(0, battery),
                water=max(0, water),
                return_reserve_ok=oxygen >= 25 and battery >= 20 and water >= 20)


def _reasons(res, m):
    r = []
    if m["status"] != "open":
        r.append("Mission is not open")
    if res["health"] < 65:
        r.append("Health score below mission minimum (65)")
    if res["work"] not in m["jobs"].split(","):
        r.append("Additional training required for this role")
    if m["sector_status"] == "hazardous" or m["hazard"] > m["max_hazard"]:
        r.append("Sector hazard exceeds mission authorization")
    if not equipment(m["hours"], m["hazard"])["return_reserve_ok"]:
        r.append("Insufficient projected return reserves")
    return r


# ---------------------------------------------------------------- reading
def list_missions(user_id):
    """Missions + 'reasons' (why this user cannot apply; empty = eligible)."""
    with _connect() as con:
        cur = con.cursor()
        try:
            res = _resident(cur, user_id)
        except ValueError:
            res = None                       # e.g. admin without resident row
        missions = _rows(cur, _MISSION_SQL + " ORDER BY m.MissionID")
        for m in missions:
            m["reasons"] = _reasons(res, m) if res else ["No resident record"]
        return missions


def my_applications(user_id):
    # report_state: None = no report yet, 0 = pending, 1 = approved, -1 = rejected
    with _connect() as con:
        cur = con.cursor()
        res = _resident(cur, user_id)
        return _rows(cur, """
            SELECT TOP 10 a.ApplicationID id, m.Title title, a.[Status] status,
                   p.Verified report_state
            FROM Explore_Applications a
            JOIN Explore_Missions m ON m.MissionID = a.MissionID
            LEFT JOIN Explore_Reports p ON p.ApplicationID = a.ApplicationID
            WHERE a.ResidentID = ? ORDER BY a.ApplicationID DESC""", res["id"])


def pending_applications(actor_id):
    _require_admin(actor_id)
    with _connect() as con:
        return _rows(con.cursor(), """
            SELECT a.ApplicationID id, a.ResidentID resident_id, m.Title title,
                   r.Work work, r.Health health
            FROM Explore_Applications a
            JOIN Explore_Missions m ON m.MissionID = a.MissionID
            JOIN Residents r ON r.ID = a.ResidentID
            WHERE a.[Status] = 'pending' ORDER BY a.ApplicationID""")


def pending_reports(actor_id):
    _require_admin(actor_id)
    with _connect() as con:
        return _rows(con.cursor(), """
            SELECT p.ReportID id, a.ResidentID resident_id, m.Title title,
                   p.ResourceFound resource, p.Findings findings
            FROM Explore_Reports p
            JOIN Explore_Applications a ON a.ApplicationID = p.ApplicationID
            JOIN Explore_Missions m ON m.MissionID = a.MissionID
            WHERE p.Verified = 0 ORDER BY p.ReportID""")


def list_sectors():
    with _connect() as con:
        return _rows(con.cursor(), """
            SELECT Code code, Name name, X x, Y y, [Status] status, Hazard hazard,
                   [Resource] resource, Confidence confidence, Notes notes
            FROM Explore_Sectors ORDER BY Code""")


# ---------------------------------------------------------------- resident actions
def apply(user_id, mission_id):
    with _connect() as con:
        cur = con.cursor()
        res = _resident(cur, user_id)
        rows = _rows(cur, _MISSION_SQL + " WHERE m.MissionID = ?", mission_id)
        if not rows:
            raise ValueError("Mission not found")
        reasons = _reasons(res, rows[0])
        if reasons:
            raise ValueError("; ".join(reasons))
        try:
            cur.execute("INSERT INTO Explore_Applications(MissionID, ResidentID) "
                        "VALUES (?, ?)", mission_id, res["id"])
            con.commit()
        except pyodbc.IntegrityError:
            raise ValueError("You have already applied for this mission") from None
    return "Application submitted for coordinator review."


def start(user_id, application_id):
    with _connect() as con:
        cur = con.cursor()
        res = _resident(cur, user_id)
        cur.execute("UPDATE Explore_Applications SET [Status]='active' "
                    "WHERE ApplicationID=? AND ResidentID=? AND [Status]='approved'",
                    application_id, res["id"])
        if not cur.rowcount:
            raise ValueError("Application must be approved before starting")
        con.commit()
    return "Mission started."


def submit_report(user_id, application_id, findings, resource):
    findings = (findings or "").strip()
    if not (10 <= len(findings) <= 2000):
        raise ValueError("Report must contain 10-2000 characters")
    if resource not in RESOURCES:
        raise ValueError("Invalid resource category")
    with _connect() as con:
        cur = con.cursor()
        res = _resident(cur, user_id)
        if not cur.execute("SELECT 1 FROM Explore_Applications WHERE ApplicationID=? "
                           "AND ResidentID=? AND [Status]='active'",
                           application_id, res["id"]).fetchone():
            raise ValueError("Mission must be active to submit a report")
        # a rejected report may be corrected and sent again (otherwise the mission stays stuck)
        cur.execute("UPDATE Explore_Reports SET Findings=?, ResourceFound=?, Verified=0, "
                    "SubmittedAt=SYSDATETIME() WHERE ApplicationID=? AND Verified=-1",
                    findings, resource, application_id)
        if cur.rowcount:
            con.commit()
            return "Corrected report submitted. Awaiting verification."
        try:
            cur.execute("INSERT INTO Explore_Reports(ApplicationID, Findings, ResourceFound) "
                        "VALUES (?,?,?)", application_id, findings, resource)
            con.commit()
        except pyodbc.IntegrityError:
            raise ValueError("A report was already submitted") from None
    return "Report submitted. Awaiting verification; no payment issued yet."


# ---------------------------------------------------------------- staff actions
def decide(actor_id, application_id, decision):
    _require_admin(actor_id)
    if decision not in ("approved", "rejected"):
        raise ValueError("Invalid decision")
    with _connect() as con:
        cur = con.cursor()
        cur.execute("UPDATE Explore_Applications SET [Status]=? "
                    "WHERE ApplicationID=? AND [Status]='pending'",
                    decision, application_id)
        if not cur.rowcount:
            raise ValueError("Only pending applications can be reviewed")
        con.commit()
    return f"Application {decision}."


def verify_report(actor_id, report_id, approved):
    _require_admin(actor_id)
    if type(approved) is not bool:
        raise ValueError("Approval must be true or false")
    with _connect() as con:
        cur = con.cursor()
        row = cur.execute("""
            SELECT p.ApplicationID, p.ResourceFound, p.Verified, a.ResidentID,
                   a.[Status], m.BaseReward, m.SectorCode
            FROM Explore_Reports p
            JOIN Explore_Applications a ON a.ApplicationID = p.ApplicationID
            JOIN Explore_Missions m ON m.MissionID = a.MissionID
            WHERE p.ReportID = ?""", report_id).fetchone()
        if not row or row.Verified != 0:
            raise ValueError("Report missing or already reviewed")
        if approved and row.Status != "active":
            raise ValueError("Mission is not active")

        # claim the report first: a double click / second admin gets rowcount 0
        cur.execute("UPDATE Explore_Reports SET Verified=? "
                    "WHERE ReportID=? AND Verified=0", 1 if approved else -1, report_id)
        if not cur.rowcount:
            raise ValueError("Report already reviewed")
        if not approved:
            con.commit()
            return "Report rejected. No payment."

        pay = row.BaseReward + (50 if row.ResourceFound != "none" else 0)
        try:
            # everything below commits together or not at all
            cur.execute("UPDATE Explore_Applications SET [Status]='completed', "
                        "CompletedAt=SYSDATETIME() WHERE ApplicationID=?", row.ApplicationID)
            cur.execute("INSERT INTO Explore_Rewards(ApplicationID, ResidentID, Amount) "
                        "VALUES (?,?,?)", row.ApplicationID, row.ResidentID, pay)
            cur.execute("UPDATE Residents SET Money = ISNULL(Money,0) + ? WHERE ID = ?",
                        pay, row.ResidentID)
            cur.execute("UPDATE Explore_Sectors SET Confidence = "
                        "CASE WHEN Confidence + 0.1 > 1 THEN 1 ELSE Confidence + 0.1 END "
                        "WHERE Code = ?", row.SectorCode)
            con.commit()
        except pyodbc.IntegrityError:
            raise ValueError("This mission was already paid") from None
    return f"Report approved. {pay} credits paid."