"""
HOLLOW-CORE, step 1: per-level population analytics.

Reads the existing `residents` table (id, work, health, family, level, money)
and summarises each of The Hollow's 10 levels.

Assumptions (all configurable / documented):
  * "Vulnerable" = health strictly below `vulnerable_threshold` (default 30).
  * "Family demand" = total number of dependents (SUM of `family`).
    `demand_units` = residents + dependents, i.e. the real number of mouths
    to feed / lungs to supply on that level. Later modules (shortage
    prediction, resource allocation) can use this as the demand baseline.
"""

from dataclasses import dataclass, asdict
import sqlite3

NUM_LEVELS = 10
DEFAULT_VULNERABLE_THRESHOLD = 30  # health < 30 counts as vulnerable


@dataclass(frozen=True)
class LevelStats:
    level: int
    population: int
    avg_health: float
    avg_wealth: float
    family_demand: int         # total dependents across residents on this level
    demand_units: int          # population + family_demand
    vulnerable_count: int
    vulnerable_pct: float      # 0-100

    def to_dict(self):
        return asdict(self)


def _empty_level(level):
    return LevelStats(level, 0, 0.0, 0.0, 0, 0, 0, 0.0)


def analyze_levels(con, vulnerable_threshold=DEFAULT_VULNERABLE_THRESHOLD,
                   num_levels=NUM_LEVELS):
    """
    Return {level: LevelStats} for every level 1..num_levels.

    Levels with no residents are still included (all zeros) so downstream
    code never has to handle a missing key.
    Runs as a single GROUP BY query, which uses idx_residents_level if present.
    """
    if not isinstance(vulnerable_threshold, (int, float)):
        raise TypeError("vulnerable_threshold must be a number")
    if not 0 <= vulnerable_threshold <= 101:
        raise ValueError("vulnerable_threshold should be between 0 and 101")

    rows = con.execute(
        """
        SELECT level,
               COUNT(*)                                        AS population,
               AVG(health)                                     AS avg_health,
               AVG(money)                                      AS avg_wealth,
               SUM(family)                                     AS family_demand,
               SUM(CASE WHEN health < ? THEN 1 ELSE 0 END)     AS vulnerable
        FROM residents
        WHERE level BETWEEN 1 AND ?
        GROUP BY level
        """,
        (vulnerable_threshold, num_levels),
    ).fetchall()

    stats = {lvl: _empty_level(lvl) for lvl in range(1, num_levels + 1)}
    for r in rows:
        lvl, pop, avg_h, avg_w, fam, vul = (
            r[0], r[1], r[2], r[3], r[4] or 0, r[5] or 0)
        stats[lvl] = LevelStats(
            level=lvl,
            population=pop,
            avg_health=round(avg_h, 2),
            avg_wealth=round(avg_w, 2),
            family_demand=fam,
            demand_units=pop + fam,
            vulnerable_count=vul,
            vulnerable_pct=round(100 * vul / pop, 2) if pop else 0.0,
        )
    return stats


def hollow_totals(stats):
    """Whole-Hollow roll-up of the per-level results."""
    pop = sum(s.population for s in stats.values())
    vul = sum(s.vulnerable_count for s in stats.values())
    fam = sum(s.family_demand for s in stats.values())
    return {
        "population": pop,
        "family_demand": fam,
        "demand_units": pop + fam,
        "vulnerable_count": vul,
        "vulnerable_pct": round(100 * vul / pop, 2) if pop else 0.0,
        "avg_health": round(
            sum(s.avg_health * s.population for s in stats.values()) / pop, 2
        ) if pop else 0.0,
        "avg_wealth": round(
            sum(s.avg_wealth * s.population for s in stats.values()) / pop, 2
        ) if pop else 0.0,
    }


def print_report(stats, threshold):
    print(f"Level analytics (vulnerable = health < {threshold})")
    print(f"{'Lvl':>3} {'Pop':>9} {'AvgHP':>6} {'AvgMoney':>9} "
          f"{'Dependents':>11} {'DemandUnits':>12} {'Vuln':>8} {'Vuln%':>6}")
    for s in stats.values():
        print(f"{s.level:>3} {s.population:>9,} {s.avg_health:>6.1f} "
              f"{s.avg_wealth:>9.1f} {s.family_demand:>11,} "
              f"{s.demand_units:>12,} {s.vulnerable_count:>8,} "
              f"{s.vulnerable_pct:>5.1f}%")
    t = hollow_totals(stats)
    print(f"{'ALL':>3} {t['population']:>9,} {t['avg_health']:>6.1f} "
          f"{t['avg_wealth']:>9.1f} {t['family_demand']:>11,} "
          f"{t['demand_units']:>12,} {t['vulnerable_count']:>8,} "
          f"{t['vulnerable_pct']:>5.1f}%")


if __name__ == "__main__":
    # Plug into the teammate's database module. Rename the import to match
    # the filename of their file (e.g. hollow_db.py).
    try:
        from hollow_db import build_database
        con = build_database(n=1_000_000)
    except ImportError:
        # Fallback: tiny standalone demo so this file runs on its own
        import random
        con = sqlite3.connect(":memory:")
        con.execute("""CREATE TABLE residents (
            id INTEGER PRIMARY KEY, work TEXT, health INTEGER,
            family INTEGER, level INTEGER, money INTEGER)""")
        con.executemany(
            "INSERT INTO residents VALUES (?,?,?,?,?,?)",
            ((i, "miner", random.randint(0, 100), random.randint(0, 7),
              random.randint(1, 10), random.randint(0, 4999))
             for i in range(1, 50_001)))
        con.execute("CREATE INDEX idx_residents_level ON residents (level)")

    THRESHOLD = 30
    results = analyze_levels(con, vulnerable_threshold=THRESHOLD)
    print_report(results, THRESHOLD)

    # Structured / dict form for the next HOLLOW-CORE modules:
    as_dicts = {lvl: s.to_dict() for lvl, s in results.items()}
    print("\nLevel 1 as dict:", as_dicts[1])
