"""
The Hollow: residents + levels + systems database (sqlite3, standard library only).

Design idea: never touch 1,000,000 resident rows every tick.
  * Systems live on levels (level_systems). Each system has a health value 0-100.
  * When a system is degraded, a *rate* is written to level_effects
    (e.g. "level 3 loses 0.5 health/sec because oxygen is down").
  * Each tick only touches ~10 level rows. Damage accumulates per level in
    level_effects.pending_* columns.
  * Pending damage is applied to residents in ONE set-based UPDATE per level
    (flush_effects), only when you choose to (event end, every N sim-minutes, GUI refresh...).
    Indexes on resident.level make that update fast.
"""

import random
import sqlite3
import time

NUM_RESIDENTS = 1_000_000
NUM_LEVELS = 10

WORKS = ["engineer", "farmer", "medic", "miner",
         "technician", "teacher", "guard", "scavenger"]
WORK_WEIGHTS = [5, 30, 8, 20, 10, 8, 4, 15]

# What each system is, which question group it belongs to, and what happens
# to residents per second when it is fully offline (status = 0).
# effect_stat: which resident column is damaged. max_rate: units/sec at status 0.
SYSTEM_TYPES = [
    # name,            group,                          effect_stat, max_rate
    ("oxygen",        "energy & infrastructure",       "health",    1.00),
    ("electricity",   "energy & infrastructure",       "health",    0.10),
    ("water",         "resource management",           "health",    0.40),
    ("food",          "resource management",           "health",    0.25),
    ("medicine",      "healthcare",                    "health",    0.15),
    ("communication", "communication & emergency",     "health",    0.02),
    ("housing",       "housing",                       "health",    0.05),
]

SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS event_log;
DROP TABLE IF EXISTS level_effects;
DROP TABLE IF EXISTS level_systems;
DROP TABLE IF EXISTS system_types;
DROP TABLE IF EXISTS residents;
DROP TABLE IF EXISTS levels;

CREATE TABLE levels (
    level       INTEGER PRIMARY KEY CHECK (level >= 1),
    name        TEXT,
    population  INTEGER NOT NULL DEFAULT 0,   -- cached; see refresh_population()
    alive       INTEGER NOT NULL DEFAULT 0    -- cached count of residents with health > 0
);

CREATE TABLE residents (
    id      INTEGER PRIMARY KEY,
    work    TEXT    NOT NULL,
    health  INTEGER NOT NULL CHECK (health BETWEEN 0 AND 100),
    family  INTEGER NOT NULL CHECK (family >= 0),
    level   INTEGER NOT NULL REFERENCES levels(level),
    money   INTEGER NOT NULL
);

-- Static definition of each kind of system
CREATE TABLE system_types (
    system      TEXT PRIMARY KEY,
    grp         TEXT NOT NULL,                       -- the track's question group
    effect_stat TEXT NOT NULL CHECK (effect_stat IN ('health','money')),
    max_rate    REAL NOT NULL                        -- loss per resident per sec at status 0
);

-- One row per (level, system): the current state, e.g. level 3 oxygen = 45
CREATE TABLE level_systems (
    level   INTEGER NOT NULL REFERENCES levels(level),
    system  TEXT    NOT NULL REFERENCES system_types(system),
    status  REAL    NOT NULL DEFAULT 100 CHECK (status BETWEEN 0 AND 100),
    PRIMARY KEY (level, system)
) WITHOUT ROWID;

-- The accumulator. One row per level. The simulation writes here, not to residents.
--   rate_health    = health points lost per resident per second RIGHT NOW (derived from systems)
--   pending_health = damage accumulated since the last flush (per resident, fractional)
CREATE TABLE level_effects (
    level          INTEGER PRIMARY KEY REFERENCES levels(level),
    rate_health    REAL NOT NULL DEFAULT 0,
    pending_health REAL NOT NULL DEFAULT 0,
    rate_money     REAL NOT NULL DEFAULT 0,
    pending_money  REAL NOT NULL DEFAULT 0
);

-- Optional: lets the GUI show a timeline and lets you audit what flush applied
CREATE TABLE event_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_time REAL NOT NULL,
    level    INTEGER,
    system   TEXT,
    message  TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX idx_residents_work       ON residents (work);
CREATE INDEX idx_residents_level      ON residents (level);
CREATE INDEX idx_residents_work_level ON residents (work, level);
CREATE INDEX idx_residents_level_health ON residents (level, health);
CREATE INDEX idx_event_log_time       ON event_log (sim_time);
"""


# ---------------------------------------------------------------- build ----

def generate_residents(n, num_levels=NUM_LEVELS):
    jobs = random.choices(WORKS, weights=WORK_WEIGHTS, k=n)
    for i in range(1, n + 1):
        yield (i, jobs[i - 1],
               random.randint(50, 100),
               random.randint(0, 7),
               random.randint(1, num_levels),
               random.randint(0, 4999))


def build_database(path=":memory:", n=NUM_RESIDENTS, num_levels=NUM_LEVELS):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    with con:
        con.executemany("INSERT INTO levels (level, name) VALUES (?, ?)",
                        [(l, f"Level {l}") for l in range(1, num_levels + 1)])
        con.executemany("INSERT INTO system_types VALUES (?, ?, ?, ?)", SYSTEM_TYPES)
        # every level starts with every system at 100%
        con.execute("""INSERT INTO level_systems (level, system, status)
                       SELECT l.level, s.system, 100 FROM levels l CROSS JOIN system_types s""")
        con.execute("INSERT INTO level_effects (level) SELECT level FROM levels")
        con.executemany("INSERT INTO residents VALUES (?, ?, ?, ?, ?, ?)",
                        generate_residents(n, num_levels))
    con.executescript(INDEXES)
    refresh_population(con)
    con.execute("ANALYZE")
    return con


# ------------------------------------------------- resident query helpers ----

def find_by_id(con, resident_id):
    return con.execute("SELECT * FROM residents WHERE id = ?", (resident_id,)).fetchone()


def find_where(con, **filters):
    allowed = {"work", "health", "family", "level", "money"}
    bad = set(filters) - allowed
    if bad:
        raise ValueError(f"Unknown columns: {bad}")
    clause = " AND ".join(f"{col} = ?" for col in filters) or "1"
    return con.execute(f"SELECT * FROM residents WHERE {clause}",
                       tuple(filters.values())).fetchall()


# ------------------------------------------------------ systems / effects ----

def set_system_status(con, level, system, status, sim_time=0.0, log=True):
    """Set one system on one level (0-100) and recompute that level's rates."""
    status = max(0.0, min(100.0, status))
    with con:
        cur = con.execute("UPDATE level_systems SET status = ? WHERE level = ? AND system = ?",
                          (status, level, system))
        if cur.rowcount == 0:
            raise ValueError(f"No system '{system}' on level {level}")
        if log:
            con.execute("INSERT INTO event_log (sim_time, level, system, message) VALUES (?,?,?,?)",
                        (sim_time, level, system, f"{system} set to {status:.0f}%"))
    recompute_rates(con, [level])


def damage_system(con, level, system, amount, sim_time=0.0):
    """Lower a system's status by `amount` points (negative = repair)."""
    row = con.execute("SELECT status FROM level_systems WHERE level = ? AND system = ?",
                      (level, system)).fetchone()
    set_system_status(con, level, system, row["status"] - amount, sim_time)


def recompute_rates(con, levels=None):
    """
    Turn system statuses into per-second rates on level_effects.
    rate = sum over systems of max_rate * (1 - status/100), grouped by the stat affected.
    Call after any status change (set_system_status already does). Touches ~10 rows.
    """
    where = ""
    params = ()
    if levels:
        where = f"WHERE ls.level IN ({','.join('?' * len(levels))})"
        params = tuple(levels)
    with con:
        con.execute(f"""
            UPDATE level_effects SET
              rate_health = COALESCE((
                  SELECT SUM(st.max_rate * (1 - ls.status / 100.0))
                  FROM level_systems ls JOIN system_types st USING (system)
                  WHERE ls.level = level_effects.level AND st.effect_stat = 'health'), 0),
              rate_money = COALESCE((
                  SELECT SUM(st.max_rate * (1 - ls.status / 100.0))
                  FROM level_systems ls JOIN system_types st USING (system)
                  WHERE ls.level = level_effects.level AND st.effect_stat = 'money'), 0)
            {"WHERE level IN (" + ",".join("?" * len(levels)) + ")" if levels else ""}
        """, params if levels else ())


def tick(con, dt):
    """
    Advance the world by dt seconds WITHOUT touching residents:
    pending += rate * dt on ~10 rows. Safe to call many times per second.
    """
    with con:
        con.execute("""UPDATE level_effects SET
                         pending_health = pending_health + rate_health * ?,
                         pending_money  = pending_money  + rate_money  * ?""", (dt, dt))


def flush_effects(con, levels=None):
    """
    Apply accumulated damage to residents, then reset the accumulators.
    One set-based UPDATE per level that has >= 1 whole point pending.
    The fractional remainder stays in pending so nothing is lost to rounding.
    Returns {level: (health_points_applied, money_applied)}.
    """
    sql = "SELECT * FROM level_effects"
    params = ()
    if levels:
        sql += f" WHERE level IN ({','.join('?' * len(levels))})"
        params = tuple(levels)
    applied = {}
    with con:
        for row in con.execute(sql, params).fetchall():
            dh = int(row["pending_health"] + 1e-9)   # whole points only (epsilon guards float error)
            dm = int(row["pending_money"] + 1e-9)
            if dh == 0 and dm == 0:
                continue
            con.execute("""UPDATE residents
                           SET health = MAX(0, health - ?),
                               money  = MAX(0, money  - ?)
                           WHERE level = ? AND health > 0""",   # the dead stop taking damage
                        (dh, dm, row["level"]))
            con.execute("""UPDATE level_effects
                           SET pending_health = pending_health - ?,
                               pending_money  = pending_money  - ?
                           WHERE level = ?""", (dh, dm, row["level"]))
            applied[row["level"]] = (dh, dm)
    return applied


def refresh_population(con):
    """Recompute cached level counts. Run after flush_effects or on a slow timer."""
    with con:
        con.execute("""UPDATE levels SET
            population = (SELECT COUNT(*) FROM residents r WHERE r.level = levels.level),
            alive      = (SELECT COUNT(*) FROM residents r
                          WHERE r.level = levels.level AND r.health > 0)""")


# ------------------------------------------------------------- reporting ----

def level_dashboard(con):
    """One cheap query for the GUI: cached counts + current rates + worst system per level."""
    return con.execute("""
        SELECT l.level, l.population, l.alive,
               e.rate_health, e.pending_health,
               (SELECT system FROM level_systems ls
                WHERE ls.level = l.level ORDER BY status ASC LIMIT 1) AS worst_system,
               (SELECT MIN(status) FROM level_systems ls WHERE ls.level = l.level) AS worst_status
        FROM levels l JOIN level_effects e USING (level) ORDER BY l.level""").fetchall()


def system_matrix(con):
    """Level x system status grid for a heat-map: rows of (level, {system: status})."""
    grid = {}
    for r in con.execute("SELECT level, system, status FROM level_systems ORDER BY level"):
        grid.setdefault(r["level"], {})[r["system"]] = r["status"]
    return grid


def level_summary(con):
    return con.execute("""SELECT level, COUNT(*) AS population, ROUND(AVG(money)) AS avg_money,
                                 ROUND(AVG(health),1) AS avg_health
                          FROM residents GROUP BY level ORDER BY level""").fetchall()


if __name__ == "__main__":
    t = time.time()
    db = build_database()
    print(f"Built {NUM_RESIDENTS:,} residents in {time.time() - t:.1f}s\n")

    # Demo: oxygen fails on level 3 for 60 simulated seconds
    set_system_status(db, 3, "oxygen", 20, sim_time=0)
    for _ in range(60):
        tick(db, dt=1.0)                       # touches 10 rows, not 100,000

    before = db.execute("SELECT ROUND(AVG(health),1) FROM residents WHERE level = 3").fetchone()[0]
    t = time.time()
    print("Applied:", flush_effects(db))
    print(f"Flush took {(time.time() - t) * 1000:.0f} ms")
    after = db.execute("SELECT ROUND(AVG(health),1) FROM residents WHERE level = 3").fetchone()[0]
    print(f"Level 3 avg health: {before} -> {after}")

    refresh_population(db)
    for r in level_dashboard(db):
        print(dict(r))
