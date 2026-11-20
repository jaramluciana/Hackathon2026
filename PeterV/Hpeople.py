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

import bisect
import random
import sqlite3
import time

NUM_RESIDENTS = 1_000_000
NUM_LEVELS = 10

# Healing: while a level's food status is >= HEAL_FOOD_MIN, living residents
# without lung disease regain health at HEAL_RATE per (scaled) second, but never
# above the food percentage (food 80% -> nobody heals past 80 health).
HEAL_FOOD_MIN = 80.0
HEAL_RATE = 0.10

# Lung-disease cure: while a level's medicine status is >= CURE_MEDICINE_MIN, sick residents are
# cured at random. The chance scales with medicine: CURE_RATE_MIN at 80% up to CURE_RATE_MAX at
# 100%. Units: fraction of sick residents cured per (scaled) second, same units as HEAL_RATE.
# At the default speed (30 scaled seconds per tick) that is ~0.15% of the sick per tick at 80%
# medicine and ~0.9% per tick at 100%.
CURE_MEDICINE_MIN = 80.0
CURE_RATE_MIN = 0.00005
CURE_RATE_MAX = 0.0003

# ---- Food & medicine stockpile -------------------------------------------------------------
# The Hollow starts with ONE stockpile of food and one of medicine, portioned out to the levels at
# build time. Residents eat it down; living farmers and medics on the level refill it (see
# PRODUCTION below). Disasters knock it down and visiting farmers/medics help refill it.
#   * portion of a level = total * weight * population / sum(weight * population)
#   * weights: the top level gets TOP_SUPPLY_WEIGHT, falling in a straight line to 1.0 at the last
#     "sufficient" level. The bottom SHORTAGE_FRACTION of the levels (level numbers count downward,
#     level 1 = top) get only SHORT_SUPPLY_WEIGHT: 2 of 10 levels, 4 of 20 - the mirror image of
#     the top levels that are shielded from power outages.
#   * every living resident consumes the SAME amount per simulated hour on every level (fair), so
#     a level with a small portion simply runs dry sooner.
# Stock is kept as the level's food/medicine STATUS (100% = the full portion), so events, healing,
# curing and damage keep working unchanged: stock units = capacity * status / 100.
SHORTAGE_FRACTION = 0.20
TOP_SUPPLY_WEIGHT = 2.0
SHORT_SUPPLY_WEIGHT = 0.3
CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR = {"food": 1.0, "medicine": 1.0}   # units; same for everyone
# Size of the stockpile, as sim-hours of consumption for the AVERAGE resident (total units =
# hours * consumption * total residents). Bigger = everything lasts longer. At the default speed
# 1 sim hour = 1 real minute: with 120, an average level lasts ~1.5 real hours, the top level
# ~3 hours, and the bottom levels ~30 minutes.
SUPPLY_HOURS_PER_RESIDENT = {"food": 120.0, "medicine": 120.0}

# Jobs. Engineers are NOT drawn by weight: every level gets roughly ENGINEERS_PER_LEVEL of them
# (they are a small specialist crew). Everyone else is drawn by these weights.
WORKS = ["farmer", "medic", "miner", "technician", "teacher", "guard", "scavenger"]
WORK_WEIGHTS = [30, 8, 20, 10, 8, 4, 15]
ENGINEERS_PER_LEVEL = 120        # generated per level, give or take ENGINEER_SPREAD
ENGINEER_SPREAD = 10
MAX_ENGINEERS_PER_LEVEL = 500    # hard cap on engineers standing on one level (home + visitors)

# Production: every LIVING farmer adds food and every LIVING medic adds medicine to the level they
# are standing on, in units per sim hour (consumption is 1 unit per resident per sim hour, above).
# Stock can't go above the level's full portion (status 100%), so surplus is wasted.
# The rate is derived from the job weights so it stays correct if you change them:
#     break-even rate = consumption / (share of residents doing that job)
#     actual rate     = break-even * SELF_SUFFICIENCY
# With 1.5 a fully staffed level makes 50% more than it eats, so stock refills after a disaster.
# Home crews alone refill slowly; visiting farmers/medics (HollowWorkers.py) make it much faster.
# If farmers/medics die, production falls with them.
SELF_SUFFICIENCY = {"food": 1.5, "medicine": 1.5}
PRODUCER_COLUMN = {"food": "farmers", "medicine": "medics"}      # levels column holding the count
PRODUCER_WORK = {"food": "farmer", "medicine": "medic"}          # residents.work value


def _job_share(work):
    return WORK_WEIGHTS[WORKS.index(work)] / sum(WORK_WEIGHTS)


PRODUCTION_PER_WORKER_PER_SIM_HOUR = {
    system: CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[system] / _job_share(work) * SELF_SUFFICIENCY[system]
    for system, work in PRODUCER_WORK.items()
}   # food ~4.75, medicine ~17.8 with the defaults

# What each system is, which question group it belongs to, and what happens
# to residents per second when it is fully offline (status = 0).
# effect_stat: which resident column is damaged. max_rate: units/sec at status 0.
# threshold: the system only hurts residents once its status falls BELOW this value. Damage
# grows smoothly from 0 at the threshold up to max_rate at status 0:
#     rate = max_rate * (threshold - status) / threshold      (when status < threshold)
# threshold 100 = hurts as soon as the system is anything less than perfect.
SYSTEM_TYPES = [
    # name,            group,                          effect_stat, max_rate, threshold
    ("oxygen",        "energy & infrastructure",       "health",    1.00,     50),
    ("electricity",   "energy & infrastructure",       "health",    0.10,     20),
    ("water",         "resource management",           "health",    0.40,     80),
    ("food",          "resource management",           "health",    0.25,     20),
    ("medicine",      "healthcare",                    "health",    0.15,     20),
    ("communication", "communication & emergency",     "health",    0.02,    100),
    ("housing",       "housing",                       "health",    0.05,     80),
]

SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS level_jobs;
DROP TABLE IF EXISTS level_supply;
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
    alive       INTEGER NOT NULL DEFAULT 0,   -- cached count of residents with health > 0
    -- worker counts = LIVING workers standing on this level right now (home crew + visitors,
    -- not counting anyone walking between levels). Kept up to date by HollowWorkers.py.
    engineers   INTEGER NOT NULL DEFAULT 0,   -- drives repair speed
    farmers     INTEGER NOT NULL DEFAULT 0,   -- they produce food
    medics      INTEGER NOT NULL DEFAULT 0    -- they produce medicine
);

CREATE TABLE residents (
    id      INTEGER PRIMARY KEY,
    work    TEXT    NOT NULL,
    health  INTEGER NOT NULL CHECK (health BETWEEN 0 AND 100),
    family  INTEGER NOT NULL CHECK (family >= 0),
    level   INTEGER NOT NULL REFERENCES levels(level),
    money   INTEGER NOT NULL,
    lung_disease INTEGER NOT NULL DEFAULT 0 CHECK (lung_disease IN (0,1)),  -- 1 = cannot heal
    moving    INTEGER NOT NULL DEFAULT 0 CHECK (moving IN (0,1)),  -- 1 = walking between levels
    away_from INTEGER REFERENCES levels(level)   -- home level while helping elsewhere, else NULL
);

-- Static definition of each kind of system
CREATE TABLE system_types (
    system      TEXT PRIMARY KEY,
    grp         TEXT NOT NULL,                       -- the track's question group
    effect_stat TEXT NOT NULL CHECK (effect_stat IN ('health','money')),
    max_rate    REAL NOT NULL,                       -- loss per resident per sec at status 0
    threshold   REAL NOT NULL DEFAULT 100 CHECK (threshold > 0 AND threshold <= 100)
                                                     -- damage only starts below this status
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
    pending_money  REAL NOT NULL DEFAULT 0,
    rate_heal      REAL NOT NULL DEFAULT 0,   -- health regained per resident per second (0 unless food is high)
    pending_heal   REAL NOT NULL DEFAULT 0,
    rate_cure      REAL NOT NULL DEFAULT 0,   -- fraction of sick residents cured per second (0 unless medicine is high)
    pending_cure   REAL NOT NULL DEFAULT 0,   -- accumulated cure probability since the last flush
    healed_to      REAL NOT NULL DEFAULT 0    -- every living resident who CAN heal is at least this
                                              -- healthy, so flush skips healing scans that would
                                              -- change nothing. Reset to 0 by damage, cures and arrivals.
);

-- Head count (alive + dead) of the travelling trades per level. Only changes when workers move
-- (HollowWorkers keeps it current), so refresh_population doesn't have to recount 1M rows.
CREATE TABLE level_jobs (
    level INTEGER NOT NULL REFERENCES levels(level),
    work  TEXT    NOT NULL,
    total INTEGER NOT NULL,
    PRIMARY KEY (level, work)
) WITHOUT ROWID;

-- Each level's portion of the food / medicine stockpile (see allocate_supplies).
-- capacity = units portioned to the level = the stock when its status is 100%.
CREATE TABLE level_supply (
    level    INTEGER NOT NULL REFERENCES levels(level),
    system   TEXT    NOT NULL REFERENCES system_types(system),
    capacity REAL    NOT NULL,
    PRIMARY KEY (level, system)
) WITHOUT ROWID;

-- Optional: lets the GUI show a timeline and lets you audit what flush applied
CREATE TABLE event_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_time REAL NOT NULL,
    level    INTEGER,
    system   TEXT,
    message  TEXT NOT NULL
);
"""

# NOTE: no index contains `health`. flush_effects rewrites health on up to ~1M rows, and every
# index containing it would have to be rewritten too (that made a full flush ~7x slower).
# idx_residents_work_level also serves "work" alone (leftmost prefix).
INDEXES = """
CREATE INDEX idx_residents_level      ON residents (level);
CREATE INDEX idx_residents_work_level ON residents (work, level);
-- tiny partial index: only dead residents are in it, so it is almost free to maintain and
-- lets refresh_population count the living as (population - dead) without scanning 1M rows
CREATE INDEX idx_residents_dead       ON residents (level, work) WHERE health = 0;
-- same idea for lung disease: only sick residents are in it, so curing never scans a whole level
CREATE INDEX idx_residents_sick       ON residents (level) WHERE lung_disease = 1;
-- workers walking between levels (a few hundred / thousand rows): they don't count anywhere
CREATE INDEX idx_residents_moving     ON residents (level, work) WHERE moving = 1;
CREATE INDEX idx_event_log_time       ON event_log (sim_time);
CREATE INDEX idx_event_log_level      ON event_log (level, id);
"""


# ---------------------------------------------------------------- build ----

def generate_residents(n, num_levels=NUM_LEVELS):
    # random.choices over a range is much faster than 4 randint() calls per resident
    jobs = random.choices(WORKS, weights=WORK_WEIGHTS, k=n)
    health = random.choices(range(50, 101), k=n)
    family = random.choices(range(0, 8), k=n)
    # Sorted, so each level's residents get consecutive ids and sit next to each other in the
    # table. flush_effects rewrites a whole level at a time, and touching one tight block of pages
    # instead of rows scattered over the entire table makes it ~2x faster.
    level = sorted(random.choices(range(1, num_levels + 1), k=n))
    # ~ENGINEERS_PER_LEVEL engineers per level, picked at random inside each level's block
    start = 0
    for lvl in range(1, num_levels + 1):
        end = bisect.bisect_right(level, lvl, lo=start)
        want = round(random.gauss(ENGINEERS_PER_LEVEL, ENGINEER_SPREAD))
        for i in random.sample(range(start, end), max(0, min(MAX_ENGINEERS_PER_LEVEL, want, end - start))):
            jobs[i] = "engineer"
        start = end
    money = random.choices(range(0, 5000), k=n)
    return zip(range(1, n + 1), jobs, health, family, level, money)


def build_database(path=":memory:", n=NUM_RESIDENTS, num_levels=NUM_LEVELS):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    with con:
        con.executemany("INSERT INTO levels (level, name) VALUES (?, ?)",
                        [(l, f"Level {l}") for l in range(1, num_levels + 1)])
        con.executemany("INSERT INTO system_types (system, grp, effect_stat, max_rate, threshold) "
                        "VALUES (?, ?, ?, ?, ?)", SYSTEM_TYPES)
        # every level starts with every system at 100%
        con.execute("""INSERT INTO level_systems (level, system, status)
                       SELECT l.level, s.system, 100 FROM levels l CROSS JOIN system_types s""")
        con.execute("INSERT INTO level_effects (level) SELECT level FROM levels")
        con.executemany("INSERT INTO residents (id, work, health, family, level, money) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        generate_residents(n, num_levels))
    con.executescript(INDEXES)
    refresh_population(con, full=True)
    allocate_supplies(con)
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
    rate = sum over systems of max_rate * (threshold - status) / threshold (only while status is
    below that system's threshold), grouped by the stat affected. Also sets rate_heal / rate_cure.
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
                  SELECT SUM(st.max_rate * MAX(0.0, st.threshold - ls.status) / st.threshold)
                  FROM level_systems ls JOIN system_types st USING (system)
                  WHERE ls.level = level_effects.level AND st.effect_stat = 'health'), 0),
              rate_money = COALESCE((
                  SELECT SUM(st.max_rate * MAX(0.0, st.threshold - ls.status) / st.threshold)
                  FROM level_systems ls JOIN system_types st USING (system)
                  WHERE ls.level = level_effects.level AND st.effect_stat = 'money'), 0),
              rate_heal = COALESCE((
                  SELECT CASE WHEN ls.status >= {HEAL_FOOD_MIN} THEN {HEAL_RATE} ELSE 0 END
                  FROM level_systems ls
                  WHERE ls.level = level_effects.level AND ls.system = 'food'), 0),
              rate_cure = COALESCE((
                  SELECT CASE WHEN ls.status >= {CURE_MEDICINE_MIN}
                              THEN {CURE_RATE_MIN} + ({CURE_RATE_MAX} - {CURE_RATE_MIN})
                                   * (ls.status - {CURE_MEDICINE_MIN}) / (100.0 - {CURE_MEDICINE_MIN})
                              ELSE 0 END
                  FROM level_systems ls
                  WHERE ls.level = level_effects.level AND ls.system = 'medicine'), 0)
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
                         pending_money  = pending_money  + rate_money  * ?,
                         pending_heal   = pending_heal   + rate_heal   * ?,
                         pending_cure   = pending_cure   + rate_cure   * ?""", (dt, dt, dt, dt))


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
            dheal = int(row["pending_heal"] + 1e-9)
            pcure = row["pending_cure"]
            if dh == 0 and dm == 0 and dheal == 0 and pcure < 1e-6:
                continue
            lvl = row["level"]
            healed_to = row["healed_to"]
            # Healing only while food is high enough; nobody is healed past the food
            # percentage (cap). cap = 0 means "no healing" in the SQL below.
            cap = 0
            if dheal:
                food = con.execute("SELECT status FROM level_systems WHERE level = ? AND system = 'food'",
                                   (lvl,)).fetchone()
                if food is not None and food["status"] >= HEAL_FOOD_MIN:
                    cap = int(food["status"] + 1e-9)
            if dh or dm:
                # damage AND healing in a single pass over the level (the dead stop taking
                # damage; the dead and lung-disease residents never heal). money is only
                # rewritten when it actually changes.
                money_sql = "money = MAX(0, money - :dm)," if dm else ""
                con.execute(f"""UPDATE residents SET {money_sql}
                                 health = CASE
                                     WHEN MAX(0, health - :dh) > 0 AND MAX(0, health - :dh) < :cap
                                          AND lung_disease = 0
                                     THEN MIN(:cap, MAX(0, health - :dh) + :heal)
                                     ELSE MAX(0, health - :dh) END
                               WHERE level = :lvl AND health > 0""",
                            {"dm": dm, "dh": dh, "cap": cap, "heal": dheal if cap else 0, "lvl": lvl})
                if dh:
                    healed_to = 0
            elif cap > healed_to:
                # heal-only: touch just the residents that can actually heal. This scans the whole
                # level, so once a pass finds nobody left to heal we remember it and stop scanning
                # until something (damage, a cure, new arrivals) makes healing possible again.
                n = con.execute("""UPDATE residents SET health = MIN(:cap, health + :heal)
                                   WHERE level = :lvl AND health > 0 AND health < :cap
                                     AND lung_disease = 0""",
                                {"cap": cap, "heal": dheal, "lvl": lvl}).rowcount
                if n == 0:
                    healed_to = cap
            if pcure >= 1e-6:
                # Medicine cures lung disease: each sick resident is cured with probability
                # pcure (the chance accumulated since the last flush). idx_residents_sick makes
                # this touch only sick residents.
                thr = int(min(1.0, pcure) * 1_000_000)
                if con.execute("""UPDATE residents SET lung_disease = 0
                                  WHERE level = ? AND lung_disease = 1
                                    AND (ABS(RANDOM()) % 1000000) < ?""", (lvl, thr)).rowcount:
                    healed_to = 0          # the cured can heal again
            else:
                pcure = 0.0
            con.execute("""UPDATE level_effects
                           SET pending_health = pending_health - ?,
                               pending_money  = pending_money  - ?,
                               pending_heal   = pending_heal   - ?,
                               pending_cure   = pending_cure   - ?,
                               healed_to      = ?
                           WHERE level = ?""", (dh, dm, dheal, pcure, healed_to, lvl))
            if dh or dm:
                applied[row["level"]] = (dh, dm)
    return applied


TRADE_WORKS = ("engineer", "farmer", "medic")


def refresh_population(con, full=False):
    """Recompute cached level counts. Run after flush_effects or on a slow timer.
    Head counts per level only change when HollowWorkers moves people (and it keeps levels.population
    and level_jobs current), so normally only the dead and the walkers are recounted, from two small
    partial indexes. full=True recounts everything (done at build; use it if you move residents
    between levels yourself)."""
    if full or con.execute("SELECT 1 FROM level_jobs LIMIT 1").fetchone() is None:
        # full recount from indexes only: idx_residents_level and idx_residents_work_level
        pop = {r[0]: r[1] for r in con.execute("SELECT level, COUNT(*) FROM residents GROUP BY level")}
        total_by_work = {(r[0], r[1]): r[2] for r in con.execute(
            f"SELECT level, work, COUNT(*) FROM residents WHERE work IN ({','.join('?' * len(TRADE_WORKS))}) "
            "GROUP BY level, work", TRADE_WORKS)}
        with con:
            con.execute("DELETE FROM level_jobs")
            con.executemany("INSERT INTO level_jobs (level, work, total) VALUES (?, ?, ?)",
                            [(l, w, n) for (l, w), n in total_by_work.items()])
    else:
        pop = {r[0]: r[1] for r in con.execute("SELECT level, population FROM levels")}
        total_by_work = {(r[0], r[1]): r[2] for r in con.execute("SELECT level, work, total FROM level_jobs")}
    # idx_residents_dead (partial: dead residents only)
    dead, dead_by_work = {}, {}
    for lvl, work, n in con.execute(
            "SELECT level, work, COUNT(*) FROM residents WHERE health = 0 GROUP BY level, work"):
        dead[lvl] = dead.get(lvl, 0) + n
        dead_by_work[(lvl, work)] = n
    # workers walking between levels don't work anywhere until they arrive (idx_residents_moving)
    moving = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT level, work, COUNT(*) FROM residents WHERE moving = 1 AND health > 0 GROUP BY level, work")}
    living = lambda lvl, work: (total_by_work.get((lvl, work), 0) - dead_by_work.get((lvl, work), 0)
                                - moving.get((lvl, work), 0))
    with con:
        con.execute("UPDATE levels SET population = 0, alive = 0, engineers = 0, farmers = 0, medics = 0")
        con.executemany(
            "UPDATE levels SET population = ?, alive = ?, engineers = ?, farmers = ?, medics = ? "
            "WHERE level = ?",
            [(p, p - dead.get(l, 0), living(l, "engineer"), living(l, "farmer"), living(l, "medic"), l)
             for l, p in pop.items()])


# ------------------------------------------------------------- supplies ----

def supply_weights(n):
    """Portion weight for each of n levels, top (level 1) first: a straight line from
    TOP_SUPPLY_WEIGHT down to 1.0, then SHORT_SUPPLY_WEIGHT for the bottom SHORTAGE_FRACTION."""
    n_short = round(n * SHORTAGE_FRACTION)          # 10 levels -> 2, 20 levels -> 4
    n_ok = n - n_short
    if n_ok <= 1:
        ok = [TOP_SUPPLY_WEIGHT] * n_ok
    else:
        ok = [TOP_SUPPLY_WEIGHT + (1.0 - TOP_SUPPLY_WEIGHT) * i / (n_ok - 1) for i in range(n_ok)]
    return ok + [SHORT_SUPPLY_WEIGHT] * n_short


def allocate_supplies(con):
    """Split the food and medicine stockpiles between the levels (more for the top, little for
    the bottom). Writes level_supply. Call once, after populations are counted."""
    levels = con.execute("SELECT level, population FROM levels ORDER BY level").fetchall()
    weights = supply_weights(len(levels))
    total_pop = sum(r["population"] for r in levels)
    weighted = sum(w * r["population"] for w, r in zip(weights, levels))
    if not weighted:
        return
    rows = []
    for system, hours in SUPPLY_HOURS_PER_RESIDENT.items():
        total_units = hours * CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[system] * total_pop
        for w, r in zip(weights, levels):
            rows.append((r["level"], system, total_units * w * r["population"] / weighted))
    with con:
        con.execute("DELETE FROM level_supply")
        con.executemany("INSERT INTO level_supply (level, system, capacity) VALUES (?, ?, ?)", rows)


def supply_report(con):
    """{level: {population, alive, food: {...}, medicine: {...}}}. Each supply has its stock in
    units, its full portion, units used and produced per sim hour, and how many sim-hours it
    lasts at the current rates (None = production keeps up, it will not run out)."""
    report = {}
    for r in con.execute("""SELECT s.level, s.system, s.capacity, ls.status, l.alive, l.population,
                                   l.farmers, l.medics
                            FROM level_supply s
                            JOIN level_systems ls ON ls.level = s.level AND ls.system = s.system
                            JOIN levels l ON l.level = s.level ORDER BY s.level"""):
        system = r["system"]
        stock = r["capacity"] * r["status"] / 100.0
        used = r["alive"] * CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[system]
        made = r[PRODUCER_COLUMN[system]] * PRODUCTION_PER_WORKER_PER_SIM_HOUR[system]
        net = used - made                                  # units lost per sim hour
        entry = report.setdefault(r["level"], {"population": r["population"], "alive": r["alive"]})
        entry[system] = {"stock": stock, "portion": r["capacity"], "used_per_hour": used,
                         "made_per_hour": made, "hours_left": stock / net if net > 0 else None}
    return report


# ------------------------------------------------------------- reporting ----

def level_dashboard(con):
    """One cheap query for the GUI: cached counts + current rates + worst system per level."""
    return con.execute("""
        SELECT l.level, l.population, l.alive, l.engineers, l.farmers, l.medics,
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
