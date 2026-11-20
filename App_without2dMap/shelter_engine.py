"""HOLLOW-SHELTER: simulation-only relocation planning for the Hollow City SQL Server app.

Uses the team's _connection() (pyodbc). No real-world safety claims.
Run setup_shelter.sql once before using database-backed functions.
"""

def _connection():
    import database  # imported only when database access is needed
    return database.connection()   # closes the connection when the with-block ends

# Statuses are SIMULATED infrastructure performance scores (0-100), not physical measurements.
CRITICAL = {"housing": 25, "oxygen": 25, "water": 20, "electricity": 15}
WARNING = {"housing": 55, "oxygen": 55, "water": 45, "electricity": 35}
ACTIVE = ("Pending", "Approved", "Arrived")
ADMIN_ID = "admin"   # same rule as the rest of the app


def _require_admin(actor_id):
    """Staff-only guard, enforced here and not only in the UI."""
    if str(actor_id or "").strip().lower() != ADMIN_ID:
        raise ValueError("Staff access required")

def assess_level(statuses):
    """Return a conservative simulated decision: unsafe / caution / normal / unknown."""
    if not statuses or "housing" not in statuses or "oxygen" not in statuses:
        return {"status": "unknown", "reasons": ["Required sensor data unavailable"], "recommend_relocation": False}
    critical, warning = [], []
    for system, threshold in CRITICAL.items():
        if system not in statuses or statuses[system] is None:
            continue
        value = float(statuses[system])
        if value <= threshold:
            critical.append(f"{system.title()} critical ({value:.0f}%)")
        elif value < WARNING[system]:
            warning.append(f"{system.title()} degraded ({value:.0f}%)")
    if critical:
        return {"status": "unsafe", "reasons": critical + warning, "recommend_relocation": True}
    if warning:
        return {"status": "caution", "reasons": warning, "recommend_relocation": False}
    return {"status": "normal", "reasons": ["No configured critical thresholds exceeded"], "recommend_relocation": False}


def rank_destinations(source_level, candidates, required=1):
    """Pure planning function; candidates contain level, capacity, occupied, reserved, statuses.
    Only safe levels with enough uncommitted space are offered. No database changes.
    """
    if required <= 0:
        raise ValueError("required must be positive")
    choices = []
    for c in candidates:
        lvl = int(c["level"])
        if lvl == int(source_level):
            continue
        # level_report() stores the system scores under "systems"
        assessment = assess_level(c.get("statuses") or c.get("systems") or {})
        if assessment["status"] != "normal":
            continue
        free = max(0, int(c["capacity"]) - int(c["occupied"]) - int(c["reserved"]))
        if free <= 0:
            continue
        choices.append({"level": lvl, "free": free, "allocatable": min(free, required),
                        "distance": abs(lvl - int(source_level)), "status": "normal"})
    choices.sort(key=lambda c: (c["distance"], -c["free"], c["level"]))
    return choices


def _systems(cur):
    rows = cur.execute("SELECT [Level], System, [Status] FROM Level_Systems").fetchall()
    result = {}
    for level, name, status in rows:
        result.setdefault(int(level), {})[str(name).lower()] = float(status)
    return result


def level_report(live=None):
    """live = {level: {system: score 0-100}} from in-memory sensors.
    For every system the WORSE of the database value and the live value wins."""
    with _connection() as conn:
        cur = conn.cursor()
        systems = _systems(cur)
        for lvl, readings in (live or {}).items():
            merged = systems.setdefault(int(lvl), {})
            for name, value in readings.items():
                merged[name] = min(merged.get(name, 100.0), float(value))
        pop = {int(r[0]): {"population": int(r[1] or 0), "alive": int(r[2] or 0)}
               for r in cur.execute("SELECT [Level], Population, Alive FROM Levels").fetchall()}
        capacities = {int(r[0]): {"capacity": int(r[1]), "occupied": int(r[2])}
                      for r in cur.execute("SELECT [Level], Capacity, Occupied FROM Shelter_Capacity").fetchall()}
        reserved = {int(r[0]): int(r[1]) for r in cur.execute(
            "SELECT DestinationLevel, SUM(PartySize) FROM Shelter_Assignments "
            "WHERE [Status] IN ('Pending','Approved') GROUP BY DestinationLevel").fetchall()}
        result = []
        for lvl in sorted(pop):
            assess = assess_level(systems.get(lvl, {}))
            cap = capacities.get(lvl, {"capacity": 0, "occupied": 0})
            result.append({"level": lvl, **pop[lvl], **assess,
                           "capacity": cap["capacity"], "occupied": cap["occupied"],
                           "reserved": reserved.get(lvl, 0), "systems": systems.get(lvl, {})})
        return result


def suggestions(source_level, party_size=1, live=None):
    report = level_report(live)
    source = next((r for r in report if r["level"] == int(source_level)), None)
    if source is None:
        raise ValueError("Unknown level")
    choices = rank_destinations(source_level, report, party_size)
    return {"source": source, "destinations": choices,
            "note": "Recommendations only. Travel routes and accessibility require coordinator verification."}


def resident_status(user_id, live=None):
    """Account ID -> registered level; do not trust an arbitrary level supplied by UI."""
    with _connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT ISNULL([Level], 1) FROM Account WHERE UserID = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("Account not found")
        lvl = int(row[0])
        assignment = cur.execute(
            "SELECT TOP 1 ID, SourceLevel, DestinationLevel, PartySize, [Status], Instructions "
            "FROM Shelter_Assignments WHERE UserID = ? AND [Status] IN ('Pending','Approved','Arrived') "
            "ORDER BY ID DESC", (user_id,)).fetchone()
    info = suggestions(lvl, live=live)
    info["user_id"] = user_id
    info["assignment"] = (dict(zip(("id", "source", "destination", "party_size", "status", "instructions"), assignment))
                          if assignment else None)
    return info


def request_relocation(user_id, party_size=1, live=None):
    """Create a request, not an automatic assignment. Coordinator must verify destination."""
    party_size = int(party_size)
    if not 1 <= party_size <= 20:
        raise ValueError("Party size must be between 1 and 20")
    info = resident_status(user_id, live)
    if info["assignment"]:
        return {"status": "existing", "id": info["assignment"]["id"]}
    if info["source"]["status"] != "unsafe":
        raise ValueError("Automatic relocation requests require a simulated unsafe-level alert; contact coordinator otherwise")
    with _connection() as conn:
        cur = conn.cursor()
        existing = cur.execute("SELECT TOP 1 ID FROM Shelter_Requests WHERE UserID=? AND [Status]='Pending' ORDER BY ID DESC", (user_id,)).fetchone()
        if existing:
            return {"status": "existing pending request", "id": int(existing[0])}
        # Requests do not reserve a destination until approved by a coordinator.
        # OUTPUT returns the new ID inside the same statement.
        # (SCOPE_IDENTITY() in a separate execute() returns NULL with pyodbc.)
        rid = int(cur.execute(
            "INSERT INTO Shelter_Requests (UserID, SourceLevel, PartySize, [Status]) "
            "OUTPUT INSERTED.ID VALUES (?, ?, ?, 'Pending')",
            (user_id, info["source"]["level"], party_size)).fetchone()[0])
        conn.commit()
    return {"status": "Pending", "id": rid}


def approve_request(request_id, destination_level, instructions, coordinator_id, live=None):
    """Atomic reservation with SQL Server locks. Staff only.
    live = in-memory readings (same format as level_report) so a destination that
    is unsafe in the alert engine is not approved.
    """
    _require_admin(coordinator_id)
    if not instructions or not instructions.strip():
        raise ValueError("Coordinator instructions are required")
    with _connection() as conn:
        cur = conn.cursor()
        try:
            req = cur.execute("SELECT UserID, SourceLevel, PartySize, [Status] "
                              "FROM Shelter_Requests WITH (UPDLOCK, HOLDLOCK) WHERE ID = ?", request_id).fetchone()
            if not req or req[3] != "Pending":
                raise ValueError("Request not found or already processed")
            user, source, party, _ = req
            if int(destination_level) == int(source):
                raise ValueError("Destination must differ from source")
            system_rows = cur.execute("SELECT System, [Status] FROM Level_Systems "
                                      "WHERE [Level] = ?", destination_level).fetchall()
            statuses = {str(r[0]).lower(): float(r[1]) for r in system_rows}
            for name, value in (live or {}).get(int(destination_level), {}).items():
                statuses[name] = min(statuses.get(name, 100.0), float(value))
            if assess_level(statuses)["status"] != "normal":
                raise ValueError("Destination is not currently assessed as safe")
            capacity = cur.execute("SELECT Capacity, Occupied FROM Shelter_Capacity WITH (UPDLOCK, HOLDLOCK) "
                                   "WHERE [Level] = ?", destination_level).fetchone()
            if not capacity:
                raise ValueError("Destination has no configured shelter capacity")
            reserved = cur.execute("SELECT COALESCE(SUM(PartySize),0) FROM Shelter_Assignments "
                                   "WHERE DestinationLevel = ? AND [Status] IN ('Pending','Approved')", destination_level).fetchone()[0]
            if int(capacity[0]) - int(capacity[1]) - int(reserved or 0) < int(party):
                raise ValueError("Not enough available shelter capacity")
            assignment_id = int(cur.execute(
                "INSERT INTO Shelter_Assignments "
                "(RequestID, UserID, SourceLevel, DestinationLevel, PartySize, [Status], Instructions, ApprovedBy) "
                "OUTPUT INSERTED.ID VALUES (?, ?, ?, ?, ?, 'Approved', ?, ?)",
                (request_id, user, source, destination_level, party,
                 instructions.strip(), coordinator_id)).fetchone()[0])
            cur.execute("UPDATE Shelter_Requests SET [Status]='Approved' WHERE ID=?", request_id)
            conn.commit()
            return assignment_id
        except Exception:
            conn.rollback()
            raise


def arrival_confirmed(assignment_id, actor_id):
    """Staff-only: transfer reservation to occupied space once party arrives."""
    _require_admin(actor_id)
    with _connection() as conn:
        cur = conn.cursor()
        try:
            a = cur.execute("SELECT DestinationLevel, PartySize, [Status] "
                            "FROM Shelter_Assignments WITH (UPDLOCK, HOLDLOCK) WHERE ID=?", assignment_id).fetchone()
            if not a or a[2] != "Approved":
                raise ValueError("Assignment is not awaiting arrival")
            cap = cur.execute("SELECT Capacity, Occupied FROM Shelter_Capacity WITH (UPDLOCK, HOLDLOCK) "
                              "WHERE [Level]=?", a[0]).fetchone()
            if not cap or int(cap[1]) + int(a[1]) > int(cap[0]):
                raise ValueError("Shelter capacity changed; cannot confirm arrival")
            cur.execute("UPDATE Shelter_Capacity SET Occupied = Occupied + ? WHERE [Level]=?", a[1], a[0])
            cur.execute("UPDATE Shelter_Assignments SET [Status]='Arrived' WHERE ID=?", assignment_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def public_instructions(info):
    """No invented routes or evacuation orders; verified staff instructions take precedence."""
    a = info.get("assignment")
    if a and a["status"] in ("Approved", "Arrived"):
        return f"Assigned temporary shelter: Level {a['destination']}. {a['instructions']}"
    if info["source"]["status"] == "unsafe":
        return ("Potentially unsafe conditions detected in the simulation. "
                "A relocation coordinator must verify safe routes and destinations. "
                "Follow official staff instructions; do not travel based solely on this recommendation.")
    if info["source"]["status"] == "unknown":
        return "Safety data unavailable. Contact the coordination team for verified instructions."
    return "No relocation order is active for your account. Monitor official notices."

# ---------------------------------------------------------------- staff tools
def pending_requests(actor_id):
    _require_admin(actor_id)
    with _connection() as conn:
        rows = conn.cursor().execute(
            "SELECT ID, UserID, SourceLevel, PartySize FROM Shelter_Requests "
            "WHERE [Status]='Pending' ORDER BY ID").fetchall()
    return [dict(id=int(r[0]), user=r[1], source=int(r[2]), party_size=int(r[3]))
            for r in rows]


def approved_assignments(actor_id):
    """Approved assignments still waiting for the party to arrive."""
    _require_admin(actor_id)
    with _connection() as conn:
        rows = conn.cursor().execute(
            "SELECT ID, UserID, SourceLevel, DestinationLevel, PartySize "
            "FROM Shelter_Assignments WHERE [Status]='Approved' ORDER BY ID").fetchall()
    return [dict(id=int(r[0]), user=r[1], source=int(r[2]),
                 destination=int(r[3]), party_size=int(r[4])) for r in rows]


def reject_request(request_id, actor_id):
    _require_admin(actor_id)
    with _connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE Shelter_Requests SET [Status]='Rejected' "
                    "WHERE ID=? AND [Status]='Pending'", request_id)
        changed = cur.rowcount
        conn.commit()
    if not changed:
        raise ValueError("Request not found or already processed")


def set_capacity(level, capacity, actor_id):
    """Set the shelter capacity of a level. Cannot go below occupied + reserved."""
    _require_admin(actor_id)
    level, capacity = int(level), int(capacity)
    if not 0 <= capacity <= 100000:
        raise ValueError("Capacity must be between 0 and 100000")
    with _connection() as conn:
        cur = conn.cursor()
        try:
            if not cur.execute("SELECT 1 FROM Levels WHERE [Level]=?", level).fetchone():
                raise ValueError("Unknown level")
            row = cur.execute("SELECT Occupied FROM Shelter_Capacity WITH (UPDLOCK, HOLDLOCK) "
                              "WHERE [Level]=?", level).fetchone()
            reserved = cur.execute(
                "SELECT COALESCE(SUM(PartySize),0) FROM Shelter_Assignments "
                "WHERE DestinationLevel=? AND [Status] IN ('Pending','Approved')",
                level).fetchone()[0]
            minimum = (int(row[0]) if row else 0) + int(reserved or 0)
            if capacity < minimum:
                raise ValueError(f"Capacity cannot be below {minimum} (occupied + reserved)")
            if row:
                cur.execute("UPDATE Shelter_Capacity SET Capacity=? WHERE [Level]=?",
                            capacity, level)
            else:
                cur.execute("INSERT INTO Shelter_Capacity ([Level], Capacity, Occupied) "
                            "VALUES (?, ?, 0)", level, capacity)
            conn.commit()
        except Exception:
            conn.rollback()
            raise