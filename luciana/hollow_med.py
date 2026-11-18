"""
HOLLOW-MED: healthcare backend for The Hollow.

Sits on top of the team's simulation database (hollow_db.py). It READS
residents / levels / level_systems / level_effects and adds its own tables
(clinics, clinic_inventory, medical_requests, medical_transfers,
emergency_responses, treatment_records).

What it can do:
  * population health monitoring per level (one cheap query)
  * forecast how many residents will need urgent care in the next N seconds
  * triage queue (heapq) ordered by urgency
  * clinic capacity + inventory, with reserves
  * recommend which clinics should send supplies / take patients, and say why
  * coordinate an emergency end to end (detect -> forecast -> plan -> track)
  * record treatments and compute performance numbers (KPIs)

Health bands and capacities are simulation rules, not medical diagnoses.
"""

import heapq
import sqlite3
from dataclasses import dataclass, field


# ======================================================================
# Configuration
# ======================================================================
@dataclass
class MedConfig:
    # Health bands (resident health 0-100; 0 = dead in the simulation)
    urgent_threshold: float = 15       # below this: "critical review"
    high_threshold: float = 35         # below this: "high priority"
    monitor_threshold: float = 55      # below this: "monitoring required"

    # Clinic sizing (treatment slots per resident; deeper levels get less)
    slots_per_resident: float = 0.18
    slot_depth_decay: float = 0.05
    center_levels: dict = field(default_factory=lambda: {
        2: (1, 3), 5: (4, 6), 8: (7, 10)})      # centre level -> levels served
    center_slots_per_resident: float = 0.04

    # Supplies (per resident served; deeper levels get less)
    kits_per_resident: float = 0.05
    emergency_oxygen_per_resident: float = 0.03
    supply_depth_decay: float = 0.06
    reserve_fraction: float = 0.20     # a clinic never gives away its last 20%
    stressed_reserve_mult: float = 1.5 # ...and keeps 50% more if its own level is struggling
    kits_per_patient: float = 0.5

    # Transport between levels
    base_eta_min: float = 5
    minutes_per_level: float = 4

    # Forecast / treatment
    horizon_sec: float = 60
    heal_per_treatment: int = 25


CFG = MedConfig()

# Which supply is consumed by which kind of emergency (default: medical kits)
ITEM_FOR = {"oxygen": "emergency_oxygen"}
ITEMS = ("medical_kits", "emergency_oxygen")

MED_SCHEMA = """

CREATE TABLE IF NOT EXISTS clinics (
    id          INTEGER PRIMARY KEY,
    level       INTEGER NOT NULL REFERENCES levels(level),
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('primary','center')),
    serves_min  INTEGER NOT NULL,
    serves_max  INTEGER NOT NULL,
    slots_total INTEGER NOT NULL,
    slots_used  INTEGER NOT NULL DEFAULT 0,
    accepting   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS clinic_inventory (
    clinic_id   INTEGER NOT NULL REFERENCES clinics(id),
    item        TEXT NOT NULL,
    qty         REAL NOT NULL,
    min_reserve REAL NOT NULL,
    burn_per_min REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (clinic_id, item)
);
CREATE TABLE IF NOT EXISTS medical_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL REFERENCES residents(id),
    level       INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    emergency   INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'Submitted',
    created     REAL NOT NULL,
    resolved    REAL
);
CREATE TABLE IF NOT EXISTS emergency_responses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       INTEGER NOT NULL,
    etype       TEXT NOT NULL,
    severity    TEXT NOT NULL,
    at_risk     INTEGER NOT NULL,
    slot_deficit INTEGER NOT NULL,
    slot_unmet  INTEGER NOT NULL,
    kit_short   REAL NOT NULL,
    kit_unmet   REAL NOT NULL,
    status      TEXT NOT NULL,
    created     REAL NOT NULL,
    closed      REAL,
    outcome     TEXT
);
CREATE TABLE IF NOT EXISTS medical_transfers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id INTEGER REFERENCES emergency_responses(id),
    kind        TEXT NOT NULL CHECK (kind IN ('supplies','slots')),
    item        TEXT,
    from_clinic INTEGER NOT NULL REFERENCES clinics(id),
    to_clinic   INTEGER NOT NULL REFERENCES clinics(id),
    qty         REAL NOT NULL,
    eta_min     REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed',
    reason      TEXT,
    created     REAL NOT NULL,
    completed   REAL
);
CREATE TABLE IF NOT EXISTS treatment_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL REFERENCES residents(id),
    clinic_id   INTEGER NOT NULL REFERENCES clinics(id),
    sim_time    REAL NOT NULL,
    health_before INTEGER NOT NULL,
    health_after  INTEGER NOT NULL,
    item        TEXT,
    qty         REAL
);

CREATE TABLE IF NOT EXISTS medical_appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL REFERENCES residents(id),
    clinic_id INTEGER NOT NULL REFERENCES clinics(id),
    sim_time REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked'
        CHECK (status IN ('booked','cancelled','completed')),
    UNIQUE(resident_id, sim_time)
);
CREATE TABLE IF NOT EXISTS medical_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level INTEGER REFERENCES levels(level),
    message TEXT NOT NULL,
    sim_time REAL NOT NULL,
    public INTEGER NOT NULL DEFAULT 1
);
"""


# ======================================================================
# Setup
# ======================================================================
def init_med(con, cfg=CFG):
    """Create the healthcare tables and seed clinics + inventory."""
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(MED_SCHEMA)
    if con.execute("SELECT COUNT(*) FROM clinics").fetchone()[0]:
        return  # idempotent: never overwrite appointments, transfers, or records
    pops = {r["level"]: r["population"] for r in
            con.execute("SELECT level, population FROM levels")}
    if not any(pops.values()):                     # cache not filled yet
        pops = {r["level"]: r["n"] for r in con.execute(
            "SELECT level, COUNT(*) AS n FROM residents GROUP BY level")}

    def stock(level, served_pop, per_res, mult=1.0):
        depth = max(0.2, 1 - cfg.supply_depth_decay * (level - 1))
        return served_pop * per_res * depth * mult

    clinics = []
    for lvl, pop in sorted(pops.items()):
        slots = int(pop * cfg.slots_per_resident *
                    (1 - cfg.slot_depth_decay * (lvl - 1)))
        clinics.append((f"Level {lvl} Clinic", "primary", lvl, lvl, lvl,
                        slots, pop, 1.0))
    for lvl, (lo, hi) in cfg.center_levels.items():
        served = sum(pops.get(l, 0) for l in range(lo, hi + 1))
        clinics.append((f"Medical Center L{lvl} (serves {lo}-{hi})", "center",
                        lvl, lo, hi, int(served * cfg.center_slots_per_resident),
                        served, 1.5))
    with con:
        for name, kind, lvl, lo, hi, slots, served, mult in clinics:
            cid = con.execute(
                """INSERT INTO clinics (level, name, kind, serves_min,
                   serves_max, slots_total) VALUES (?,?,?,?,?,?)""",
                (lvl, name, kind, lo, hi, slots)).lastrowid
            for item, per in (("medical_kits", cfg.kits_per_resident),
                              ("emergency_oxygen",
                               cfg.emergency_oxygen_per_resident)):
                qty = stock(lvl, served, per, mult)
                con.execute("INSERT INTO clinic_inventory VALUES (?,?,?,?,0)",
                            (cid, item, qty, qty * cfg.reserve_fraction))


# ======================================================================
# Conditions and monitoring
# ======================================================================
def condition(status):
    """Map a 0-100 system status to the label shown to residents."""
    if status >= 75:
        return "Normal"
    if status >= 40:
        return "Warning"
    if status >= 5:
        return "Critical"
    return "Unavailable"


def level_conditions(con, level):
    return {r["system"]: {"status": r["status"], "label": condition(r["status"])}
            for r in con.execute(
                "SELECT system, status FROM level_systems WHERE level = ?",
                (level,))}


def health_band(health, cfg=CFG):
    if health <= 0:
        return "deceased"
    if health < cfg.urgent_threshold:
        return "critical review"
    if health < cfg.high_threshold:
        return "high priority"
    if health < cfg.monitor_threshold:
        return "monitoring required"
    return "stable"


def health_bands(con, cfg=CFG):
    """One indexed aggregate query: {level: counts per health band}."""
    rows = con.execute(
        """SELECT level, COUNT(*) AS pop, SUM(health > 0) AS alive,
                  AVG(CASE WHEN health > 0 THEN health END) AS avg_health,
                  SUM(health > 0 AND health < ?)  AS critical,
                  SUM(health >= ? AND health < ?) AS high,
                  SUM(health >= ? AND health < ?) AS monitor
           FROM residents GROUP BY level ORDER BY level""",
        (cfg.urgent_threshold,
         cfg.urgent_threshold, cfg.high_threshold,
         cfg.high_threshold, cfg.monitor_threshold)).fetchall()
    return {r["level"]: dict(r) for r in rows}


def _clinic(con, level):
    return con.execute("SELECT * FROM clinics WHERE level = ? AND kind = 'primary'",
                       (level,)).fetchone()


def forecast_level(con, level, horizon=None, cfg=CFG):
    """
    How many residents will need urgent care within `horizon` simulated seconds,
    assuming conditions stay as they are now.

    Uses the accumulated-but-unapplied damage (pending_health) plus
    rate_health * horizon, and counts residents who fall into the urgent band.
    Two indexed range counts, so it is fast even with a million residents.
    """
    h = cfg.horizon_sec if horizon is None else horizon
    if h < 0:
        raise ValueError("forecast horizon must be nonnegative")
    e = con.execute("SELECT rate_health, pending_health FROM level_effects "
                    "WHERE level = ?", (level,)).fetchone()
    rate, pend = e["rate_health"], e["pending_health"]
    loss_h = pend + rate * h
    T = cfg.urgent_threshold

    # Count living residents whose CURRENT score is in the urgent band.
    # Pending damage is already accrued but not applied to resident rows.
    now = con.execute(
        "SELECT COUNT(*) FROM residents WHERE level=? AND health>0 AND health<?",
        (level, T)).fetchone()[0]
    # Projected urgent survivors: after pending + future damage, but still alive.
    total = con.execute(
        "SELECT COUNT(*) FROM residents WHERE level=? AND health>? AND health<?",
        (level, loss_h, T + loss_h)).fetchone()[0]
    lethal = con.execute(
        "SELECT COUNT(*) FROM residents WHERE level=? AND health>0 AND health<=?",
        (level, loss_h)).fetchone()[0]
    # Newly urgent residents among those not already urgent, excluding projected deaths.
    additional = con.execute(
        "SELECT COUNT(*) FROM residents WHERE level=? AND health>=? AND health>? AND health<?",
        (level, T, loss_h, T + loss_h)).fetchone()[0]
    clinic = _clinic(con, level)
    free = clinic["slots_total"] - clinic["slots_used"]
    return {
        "level": level, "horizon": h, "rate": rate,
        "urgent_now": now, "projected_total": total,
        "additional": additional, "deaths_risk": lethal,
        "free_slots": free, "deficit": max(0, total - free),
    }


def population_dashboard(con, cfg=CFG, horizon=None):
    """One row per level for the staff portal."""
    bands = health_bands(con, cfg)
    out = []
    for lvl, b in bands.items():
        f = forecast_level(con, lvl, horizon, cfg)
        conds = level_conditions(con, lvl)
        worst = min(conds, key=lambda s: conds[s]["status"])
        out.append({**b, "rate_health": f["rate"],
                    "review_pct": round(100 * b["critical"] / max(1, b["alive"]), 1),
                    "free_slots": f["free_slots"], "projected_urgent": f["projected_total"],
                    "deficit": f["deficit"], "worst_system": worst,
                    "worst_label": conds[worst]["label"]})
    return out


# ======================================================================
# Triage (priority queue)
# ======================================================================
def triage(con, level, limit=10, now=0.0, cfg=CFG, scan=300):
    """
    Review order for a level, most urgent first (heapq).
    Candidates: open medical requests + the `scan` lowest-health living
    residents (uses the (level, health) index, never scans the whole level).
    Lower score = more urgent.
    """
    rate = con.execute("SELECT rate_health FROM level_effects WHERE level=?",
                       (level,)).fetchone()["rate_health"]
    cands = {}
    for r in con.execute("SELECT id, health FROM residents WHERE level=? AND "
                         "health>0 ORDER BY health LIMIT ?", (level, scan)):
        cands[r["id"]] = {"resident": r["id"], "health": r["health"],
                          "emergency": False, "wait": 0.0}
    for q in con.execute(
            """SELECT q.resident_id, q.emergency, q.created, r.health
               FROM medical_requests q JOIN residents r ON r.id = q.resident_id
               WHERE q.level=? AND q.status IN ('Submitted','Under review')
                 AND r.health > 0""", (level,)):
        c = cands.setdefault(q["resident_id"], {"resident": q["resident_id"],
                                                "health": q["health"]})
        c["emergency"] = bool(q["emergency"])
        c["wait"] = max(0.0, (now - q["created"]) / 60)

    heap = []
    for c in cands.values():
        mins_left = c["health"] / (rate * 60) if rate > 0 else float("inf")
        score = (c["health"] - (60 if c["emergency"] else 0)
                 - min(20, c["wait"] * 0.2) - (15 if mins_left < 10 else 0))
        why = [f"health {c['health']}"]
        if c["emergency"]:
            why.append("emergency request")
        if c["wait"] >= 5:
            why.append(f"waiting {c['wait']:.0f} min")
        if mins_left < 10:
            why.append("could reach 0 in under 1 min at current decline" if mins_left < 1 else f"could reach 0 in ~{mins_left:.0f} min at current decline")
        heapq.heappush(heap, (score, c["resident"], "; ".join(why)))

    out = []
    for _ in range(min(limit, len(heap))):
        score, rid, why = heapq.heappop(heap)
        cat = ("Critical review" if score < 10 else "High priority"
               if score < 30 else "Standard priority" if score < 50
               else "Routine monitoring")
        out.append({"resident": rid, "score": round(score, 1),
                    "category": cat, "why": why})
    return out


# ======================================================================
# Requests, treatment
# ======================================================================
def submit_request(con, resident_id, kind="General health concern",
                   emergency=False, sim_time=0.0):
    r = con.execute("SELECT level, health FROM residents WHERE id=?",
                    (resident_id,)).fetchone()
    if r is None:
        raise ValueError("unknown resident")
    with con:
        rid = con.execute(
            "INSERT INTO medical_requests (resident_id, level, kind, emergency, "
            "created) VALUES (?,?,?,?,?)",
            (resident_id, r["level"], kind, int(emergency), sim_time)).lastrowid
    msg = ("Emergency request submitted; awaiting staff acknowledgment."
           if emergency else "Request received.")
    return {"tracking_number": rid, "status": "Submitted", "message": msg}


def resolve_request(con, request_id, sim_time, status="Completed"):
    if status not in ("Completed", "Cancelled", "Under review", "Assigned"):
        raise ValueError("invalid request status")
    with con:
        cur = con.execute("UPDATE medical_requests SET status=?, resolved=? WHERE id=?",
                    (status, sim_time if status in ("Completed", "Cancelled") else None, request_id))
        if cur.rowcount != 1:
            raise ValueError("unknown request")


def record_treatment(con, resident_id, clinic_id, sim_time=0.0, item="medical_kits",
                     qty=1.0, cfg=CFG):
    """Consume supplies and a slot, heal the resident, log it. Never revives the dead."""
    if qty <= 0 or item not in ITEMS:
        raise ValueError("invalid treatment supply or quantity")
    r = con.execute("SELECT health FROM residents WHERE id=?",
                    (resident_id,)).fetchone()
    if r is None:
        raise ValueError("unknown resident")
    if r["health"] <= 0:
        return {"ok": False, "reason": "resident is deceased; treatment cannot restore"}
    c = con.execute("SELECT * FROM clinics WHERE id=?", (clinic_id,)).fetchone()
    if c is None:
        raise ValueError("unknown clinic")
    inv = con.execute("SELECT qty FROM clinic_inventory WHERE clinic_id=? AND item=?",
                      (clinic_id, item)).fetchone()
    if c["slots_used"] >= c["slots_total"]:
        return {"ok": False, "reason": "no free treatment slot"}
    if inv is None or inv["qty"] < qty:
        return {"ok": False, "reason": f"not enough {item}"}
    after = min(100, r["health"] + cfg.heal_per_treatment)
    with con:
        # One synchronous treatment occupies a slot for its duration and releases it.
        con.execute("UPDATE clinics SET slots_used=slots_used+1 WHERE id=?", (clinic_id,))
        con.execute("UPDATE residents SET health=? WHERE id=?", (after, resident_id))
        con.execute("UPDATE clinic_inventory SET qty = qty - ? WHERE clinic_id=? "
                    "AND item=?", (qty, clinic_id, item))
        con.execute("INSERT INTO treatment_records (resident_id, clinic_id, sim_time,"
                    " health_before, health_after, item, qty) VALUES (?,?,?,?,?,?,?)",
                    (resident_id, clinic_id, sim_time, r["health"], after, item, qty))
        con.execute("UPDATE clinics SET slots_used=slots_used-1 WHERE id=?", (clinic_id,))
    return {"ok": True, "health_before": r["health"], "health_after": after}


# ======================================================================
# Resource optimisation between levels
# ======================================================================
def _comm_status(con, level):
    return con.execute("SELECT status FROM level_systems WHERE level=? AND "
                       "system='communication'", (level,)).fetchone()["status"]


def _worst_status(con, level):
    return con.execute("SELECT MIN(status) AS s FROM level_systems WHERE level=?",
                       (level,)).fetchone()["s"]


def _pending_out(con, clinic_id, kind, item=None):
    q = ("SELECT COALESCE(SUM(qty),0) FROM medical_transfers WHERE from_clinic=? "
         "AND kind=? AND status IN ('proposed','approved')")
    p = [clinic_id, kind]
    if item:
        q += " AND item=?"
        p.append(item)
    return con.execute(q, p).fetchone()[0]


def plan_support(con, level, kind, needed, item=None, emergency_id=None,
                 sim_time=0.0, horizon=None, cfg=CFG, persist=True):
    """
    Find clinics that can help `level` with `needed` units.
      kind='supplies': donors send `item`.
      kind='slots'   : donors take patients into their treatment slots.
    A donor only offers what is left AFTER keeping its reserve (bigger reserve
    if its own level is in trouble) and after its own projected demand.
    Donors are used nearest-first (communication problems make a level
    effectively "farther"; a level with comms down is skipped).
    Proposals are saved as 'proposed' transfers that staff must approve.
    """
    if kind not in ("supplies", "slots") or needed < 0:
        raise ValueError("invalid support request")
    if kind == "supplies" and item not in ITEMS:
        raise ValueError("unknown supply item")
    target = _clinic(con, level)
    if target is None:
        raise ValueError("unknown target level")
    donors, skipped = [], []
    own_demand = {}
    for c in con.execute("SELECT * FROM clinics WHERE id != ?", (target["id"],)):
        comm = _comm_status(con, c["level"])
        if comm < 10:
            skipped.append(f"{c['name']}: communication down, can't coordinate")
            continue
        stressed = _worst_status(con, c["level"]) < 50
        if kind == "slots":
            if c["kind"] == "primary":
                if c["level"] not in own_demand:
                    own_demand[c["level"]] = forecast_level(
                        con, c["level"], horizon, cfg)["projected_total"]
                own = own_demand[c["level"]]
            else:
                own = 0
            reserve = cfg.reserve_fraction * c["slots_total"] * (
                cfg.stressed_reserve_mult if stressed else 1)
            free = (c["slots_total"] - c["slots_used"]
                    - _pending_out(con, c["id"], "slots"))
            surplus = free - reserve - own
        else:
            inv = con.execute("SELECT qty, min_reserve FROM clinic_inventory "
                              "WHERE clinic_id=? AND item=?",
                              (c["id"], item)).fetchone()
            if inv is None:
                continue
            reserve = inv["min_reserve"] * (
                cfg.stressed_reserve_mult if stressed else 1)
            surplus = inv["qty"] - _pending_out(con, c["id"], "supplies", item) - reserve
        if surplus < 1:
            skipped.append(f"{c['name']}: no spare after reserve")
            continue
        dist = abs(c["level"] - level)
        eta = (cfg.base_eta_min + cfg.minutes_per_level * dist) * (
            1 + (100 - comm) / 100)
        donors.append((eta, c, surplus, reserve, dist, stressed, comm))
    donors.sort(key=lambda d: d[0])

    left, proposals = needed, []
    for eta, c, surplus, reserve, dist, stressed, comm in donors:
        if left <= 0:
            break
        qty = min(left, surplus)
        left -= qty
        why = (f"{c['name']}: {dist} level(s) away, ETA {eta:.0f} min; can spare "
               f"{surplus:,.0f} after keeping a reserve of {reserve:,.0f}")
        if stressed:
            why += " (reserve raised: its own level has failing systems)"
        if comm < 100:
            why += f" (communication {comm:.0f}%, slower)"
        proposals.append({"from_clinic": c["id"], "name": c["name"],
                          "qty": qty, "eta": eta, "why": why})
        if persist:
            with con:
                con.execute(
                    "INSERT INTO medical_transfers (emergency_id, kind, item, "
                    "from_clinic, to_clinic, qty, eta_min, reason, created) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (emergency_id, kind, item, c["id"], target["id"], qty, eta,
                     why, sim_time))
    return {"needed": needed, "planned": needed - max(0, left),
            "unmet": max(0.0, left), "proposals": proposals, "skipped": skipped}


def approve_transfer(con, transfer_id):
    with con:
        con.execute("UPDATE medical_transfers SET status='approved' "
                    "WHERE id=? AND status='proposed'", (transfer_id,))


def reject_transfer(con, transfer_id):
    with con:
        con.execute("UPDATE medical_transfers SET status='rejected' "
                    "WHERE id=? AND status IN ('proposed','approved')", (transfer_id,))


def complete_transfer(con, transfer_id, sim_time=0.0):
    """Move the stock / slots for real. Re-checks the donor's reserve first."""
    t = con.execute("SELECT * FROM medical_transfers WHERE id=?",
                    (transfer_id,)).fetchone()
    if t["status"] != "approved":
        return {"ok": False, "reason": f"transfer is '{t['status']}', must be approved"}
    with con:
        if t["kind"] == "supplies":
            inv = con.execute("SELECT qty, min_reserve FROM clinic_inventory WHERE "
                              "clinic_id=? AND item=?", (t["from_clinic"], t["item"])
                              ).fetchone()
            donor_level = con.execute("SELECT level FROM clinics WHERE id=?", (t["from_clinic"],)).fetchone()[0]
            stressed = _worst_status(con, donor_level) < 50
            required_reserve = inv["min_reserve"] * (CFG.stressed_reserve_mult if stressed else 1)
            other_reserved = con.execute("SELECT COALESCE(SUM(qty),0) FROM medical_transfers WHERE from_clinic=? AND kind='supplies' AND item=? AND id!=? AND status IN ('proposed','approved')", (t["from_clinic"], t["item"], transfer_id)).fetchone()[0]
            if inv["qty"] - t["qty"] - other_reserved < required_reserve - 1e-6:   # tolerance for float rounding
                con.execute("UPDATE medical_transfers SET status='failed' WHERE id=?",
                            (transfer_id,))
                return {"ok": False, "reason": "would breach donor's minimum reserve"}
            con.execute("UPDATE clinic_inventory SET qty = qty - ? WHERE clinic_id=? "
                        "AND item=?", (t["qty"], t["from_clinic"], t["item"]))
            con.execute("""INSERT INTO clinic_inventory VALUES (?,?,?,0,0)
                           ON CONFLICT(clinic_id, item) DO UPDATE SET qty = qty + ?""",
                        (t["to_clinic"], t["item"], t["qty"], t["qty"]))
        else:
            c = con.execute("SELECT slots_total, slots_used FROM clinics WHERE id=?",
                            (t["from_clinic"],)).fetchone()
            other_reserved = con.execute("SELECT COALESCE(SUM(qty),0) FROM medical_transfers WHERE from_clinic=? AND kind='slots' AND id!=? AND status IN ('proposed','approved')", (t["from_clinic"], transfer_id)).fetchone()[0]
            if c["slots_used"] + t["qty"] + other_reserved > c["slots_total"]:
                con.execute("UPDATE medical_transfers SET status='failed' WHERE id=?",
                            (transfer_id,))
                return {"ok": False, "reason": "donor clinic no longer has the slots"}
            # A slot transfer is a capacity reservation, NOT a patient movement.
            # No occupancy changes until a real patient is assigned.
            pass
        con.execute("UPDATE medical_transfers SET status='completed', completed=? "
                    "WHERE id=?", (sim_time, transfer_id))
    return {"ok": True}


# ======================================================================
# Emergency coordination
# ======================================================================
def coordinate_emergency(con, level, etype, sim_time=0.0, horizon=None, cfg=CFG):
    """
    1 detect  2 identify level  3 estimate people at risk  4 predict extra demand
    5 check local capacity  6 find donors  7 recommend assistance
    8 create requests/notifications  9 track  10 re-plan when called again.

    Calling it again for the same open emergency re-plans: earlier
    still-unapproved proposals are cancelled and new ones computed from the
    current conditions.
    """
    conds = level_conditions(con, level)
    status = (conds[etype]["status"] if etype in conds
              else min(c["status"] for c in conds.values()))
    severity = condition(status)
    f = forecast_level(con, level, horizon, cfg)
    item = ITEM_FOR.get(etype, "medical_kits")

    row = con.execute("SELECT id FROM emergency_responses WHERE level=? AND etype=? "
                      "AND closed IS NULL", (level, etype)).fetchone()
    with con:
        if row:
            eid = row["id"]
            con.execute("UPDATE medical_transfers SET status='cancelled' WHERE "
                        "emergency_id=? AND status='proposed'", (eid,))
        else:
            eid = con.execute(
                "INSERT INTO emergency_responses (level, etype, severity, at_risk,"
                " slot_deficit, slot_unmet, kit_short, kit_unmet, status, created)"
                " VALUES (?,?,?,?,0,0,0,0,'open',?)",
                (level, etype, severity, f["projected_total"], sim_time)).lastrowid

    local = con.execute("SELECT qty FROM clinic_inventory WHERE clinic_id=? AND "
                        "item=?", (_clinic(con, level)["id"], item)).fetchone()["qty"]
    kits_required = f["additional"] * cfg.kits_per_patient
    kits_short = max(0.0, kits_required - local)

    slots = plan_support(con, level, "slots", f["deficit"], None, eid, sim_time,
                         horizon, cfg) if f["deficit"] else \
        {"needed": 0, "planned": 0, "unmet": 0, "proposals": [], "skipped": []}
    kits = plan_support(con, level, "supplies", kits_short, item, eid, sim_time,
                        horizon, cfg) if kits_short else \
        {"needed": 0, "planned": 0, "unmet": 0, "proposals": [], "skipped": []}

    if f["deficit"] == 0 and kits_short == 0:
        state = "within_capacity"
    elif slots["unmet"] < 1 and kits["unmet"] < 1:
        state = "proposed_coverage"
    else:
        state = "partially_covered"
    with con:
        con.execute("UPDATE emergency_responses SET severity=?, at_risk=?, "
                    "slot_deficit=?, slot_unmet=?, kit_short=?, kit_unmet=?, status=? "
                    "WHERE id=?", (severity, f["projected_total"], f["deficit"],
                                   int(slots["unmet"]), kits_short, kits["unmet"],
                                   state, eid))

    L = [f"EMERGENCY #{eid}: Level {level} {etype} is {severity} "
         f"({status:.0f}%). Health loss on this level: {f['rate']:.2f} pts/sec per resident.",
         f"1. At risk within {f['horizon']:.0f}s: {f['urgent_now']:,} residents already "
         f"need urgent review; {f['additional']:,} more expected "
         f"(projected surviving urgent {f['projected_total']:,}). About {f['deaths_risk']:,} could reach zero health "
         f"if nothing improves.",
         f"2. Local urgent-care capacity: {f['free_slots']:,} free slots, so a "
         f"projected deficit of {f['deficit']:,}."]
    if f["deficit"]:
        L.append(f"3. Patient capacity: {slots['planned']:,.0f} of {f['deficit']:,} "
                 f"deficit covered by redirecting patients:")
        L += [f"   - {p['qty']:,.0f} patients -> {p['why']}" for p in slots["proposals"]]
        if slots["unmet"] >= 1:
            L.append(f"   STILL SHORT by {slots['unmet']:,.0f} slots. {len(slots['skipped'])}"
                     f" clinic(s) could not help (reserves, own demand or comms).")
    if kits_short:
        L.append(f"4. {item.replace('_', ' ').capitalize()}: need ~{kits_required:,.0f}, "
                 f"have {local:,.0f}, short {kits_short:,.0f}; recommended transfers:")
        L += [f"   - {p['qty']:,.0f} from {p['why']}" for p in kits["proposals"]]
        if kits["unmet"] >= 1:
            L.append(f"   STILL SHORT by {kits['unmet']:,.0f}. Escalate: request "
                     f"production or rationing.")
    if state == "within_capacity":
        L.append("No outside help needed: local capacity and stock are enough.")
    covered = f["deficit"] - slots["unmet"]
    if f["deficit"]:
        L.append(f"Outcome if approved: unserved urgent patients "
                 f"{f['deficit']:,} -> {slots['unmet']:,.0f} "
                 f"({100 * covered / f['deficit']:.0f}% of the deficit covered).")
    L.append("All proposals await approval by an emergency coordinator.")
    return {"emergency_id": eid, "state": state, "forecast": f,
            "slots": slots, "kits": kits, "explanation": L,
            "text": "\n".join(L)}


def close_emergency(con, emergency_id, sim_time, outcome="resolved"):
    with con:
        con.execute("UPDATE emergency_responses SET closed=?, outcome=? WHERE id=?",
                    (sim_time, outcome, emergency_id))


# ======================================================================
# Performance numbers
# ======================================================================
def kpis(con):
    one = lambda q: con.execute(q).fetchone()[0]
    em_req = one("SELECT COUNT(*) FROM medical_requests WHERE emergency=1")
    em_done = one("SELECT COUNT(*) FROM medical_requests WHERE emergency=1 "
                  "AND status='Completed'")
    avg_resp = con.execute("SELECT AVG(resolved - created) FROM medical_requests "
                           "WHERE status='Completed'").fetchone()[0]
    em_total = one("SELECT COUNT(*) FROM emergency_responses")
    em_ok = one("SELECT COUNT(*) FROM emergency_responses WHERE status IN "
                "('covered','within_capacity')")
    return {
        "urgent_requests_served_pct": round(100 * em_done / em_req, 1) if em_req else None,
        "avg_response_time_sec": round(avg_resp, 1) if avg_resp is not None else None,
        "unresolved_emergencies": one("SELECT COUNT(*) FROM emergency_responses "
                                      "WHERE closed IS NULL"),
        "slot_utilisation_pct": round(100 * one("SELECT SUM(slots_used) FROM clinics")
                                      / one("SELECT SUM(slots_total) FROM clinics"), 1),
        "supply_shortages": one("SELECT COUNT(*) FROM clinic_inventory "
                                "WHERE qty < min_reserve"),
        "transfers_completed": one("SELECT COUNT(*) FROM medical_transfers "
                                   "WHERE status='completed'"),
        "transfers_failed": one("SELECT COUNT(*) FROM medical_transfers "
                                "WHERE status='failed'"),
        "emergencies_within_local_capacity_pct": round(100 * em_ok / em_total, 1) if em_total else None,
        "slot_deficit_total": one("SELECT COALESCE(SUM(slot_deficit),0) FROM "
                                  "emergency_responses"),
        "slot_deficit_unmet_after_plan": one("SELECT COALESCE(SUM(slot_unmet),0) FROM "
                                             "emergency_responses"),
    }


# ======================================================================
# Resident-facing helpers
# ======================================================================
def resident_dashboard(con, resident_id, cfg=CFG):
    r = con.execute("SELECT * FROM residents WHERE id=?", (resident_id,)).fetchone()
    if r is None:
        raise ValueError("unknown resident")
    conds = level_conditions(con, r["level"])
    clinic = _clinic(con, r["level"])
    free = clinic["slots_total"] - clinic["slots_used"]
    if clinic["accepting"] and free > 0:
        suggestion = f"{clinic['name']} (free slots: {free:,})"
    else:
        alt = con.execute(
            "SELECT * FROM clinics WHERE accepting=1 AND slots_total > slots_used "
            "ORDER BY ABS(level - ?) LIMIT 1", (r["level"],)).fetchone()
        suggestion = (f"{alt['name']} (your local clinic is full)" if alt
                      else "No clinic available; submit an assistance request")
    return {"resident": resident_id, "level": r["level"], "health": r["health"],
            "status": health_band(r["health"], cfg),
            "conditions": {s: c["label"] for s, c in conds.items()},
            "suggested_clinic": suggestion,
            "open_requests": [dict(q) for q in con.execute(
                "SELECT id, kind, status FROM medical_requests WHERE resident_id=? "
                "AND status NOT IN ('Completed','Cancelled')", (resident_id,))]}


# ======================================================================
# Demo
# ======================================================================
if __name__ == "__main__":
    import sys
    import hollow_db as sim

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    db = sim.build_database(n=n)
    init_med(db)

    print("== Population health (per level) ==")
    print(f"{'lvl':>3} {'alive':>8} {'avgHP':>6} {'critical':>9} "
          f"{'free slots':>11} {'worst system':>16}")
    for d in population_dashboard(db):
        print(f"{d['level']:>3} {d['alive']:>8,} {d['avg_health']:>6.1f} "
              f"{d['critical']:>9,} {d['free_slots']:>11,} "
              f"{d['worst_system'] + ' ' + d['worst_label']:>16}")

    # The infrastructure simulation breaks level 3 oxygen
    sim.set_system_status(db, 3, "oxygen", 70, sim_time=0)
    print("\n== Emergency: Level 3 oxygen drops to 70% ==")
    res = coordinate_emergency(db, 3, "oxygen", sim_time=0)
    print(res["text"])

    # Staff approve and carry out the transfers
    for t in db.execute("SELECT id FROM medical_transfers WHERE status='proposed'"
                        ).fetchall():
        approve_transfer(db, t["id"])
        complete_transfer(db, t["id"], sim_time=600)

    print("\n== Triage queue, Level 3 (top 5) ==")
    for q in triage(db, 3, limit=5):
        print(f"  resident {q['resident']:>7}  {q['category']:<18} {q['why']}")

    print("\n== KPIs ==")
    for k, v in kpis(db).items():
        print(f"  {k}: {v}")

# ======================================================================
# Resident-facing scheduling and notifications
# ======================================================================
def book_appointment(con, resident_id, clinic_id, sim_time):
    if sim_time < 0:
        raise ValueError("appointment time must be nonnegative")
    resident = con.execute("SELECT id FROM residents WHERE id=? AND health>0", (resident_id,)).fetchone()
    clinic = con.execute("SELECT id, accepting FROM clinics WHERE id=?", (clinic_id,)).fetchone()
    if resident is None or clinic is None or not clinic["accepting"]:
        raise ValueError("resident or accepting clinic not found")
    with con:
        booked = con.execute("SELECT COUNT(*) FROM medical_appointments WHERE clinic_id=? AND sim_time=? AND status='booked'", (clinic_id, sim_time)).fetchone()[0]
        capacity = con.execute("SELECT slots_total FROM clinics WHERE id=?", (clinic_id,)).fetchone()[0]
        if booked >= capacity:
            raise ValueError("appointment time is fully booked")
        return con.execute("INSERT INTO medical_appointments (resident_id,clinic_id,sim_time) VALUES (?,?,?)", (resident_id,clinic_id,sim_time)).lastrowid


def cancel_appointment(con, appointment_id, resident_id):
    with con:
        cur = con.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=? AND resident_id=? AND status='booked'", (appointment_id,resident_id))
        return cur.rowcount == 1


def publish_notification(con, level, message, sim_time=0.0):
    if not message.strip():
        raise ValueError("message cannot be empty")
    if level is not None and con.execute("SELECT 1 FROM levels WHERE level=?", (level,)).fetchone() is None:
        raise ValueError("unknown level")
    with con:
        return con.execute("INSERT INTO medical_notifications(level,message,sim_time) VALUES (?,?,?)", (level,message,sim_time)).lastrowid


def resident_notifications(con, resident_id):
    resident = con.execute("SELECT level FROM residents WHERE id=?", (resident_id,)).fetchone()
    if resident is None:
        raise ValueError("unknown resident")
    return [dict(r) for r in con.execute("SELECT id,level,message,sim_time FROM medical_notifications WHERE public=1 AND (level=? OR level IS NULL) ORDER BY sim_time DESC,id DESC", (resident["level"],))]
