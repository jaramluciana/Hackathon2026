# This is a sample Python script.

# Press Ctrl+F5 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

"""
The Hollow: residents database in Python + SQL (sqlite3, standard library only).

Replaces the AVL tree + dictionary secondary indexes with a SQL table and indexes.
Each resident has: id, work, health, family, level, money.
"""

import random
import sqlite3
import time

NUM_RESIDENTS = 1_000_000
WORKS = ["engineer", "farmer", "medic", "miner",
         "technician", "teacher", "guard", "scavenger"]

# Same order as WORKS; these sum to 100, so each number is a percentage
WORK_WEIGHTS = [5, 30, 8, 20, 10, 8, 4, 15]

SCHEMA = """
DROP TABLE IF EXISTS residents;

CREATE TABLE residents (
    id      INTEGER PRIMARY KEY,
    work    TEXT    NOT NULL,
    health  INTEGER NOT NULL CHECK (health BETWEEN 0 AND 100),
    family  INTEGER NOT NULL CHECK (family >= 0),
    level   INTEGER NOT NULL CHECK (level >= 1),
    money   INTEGER NOT NULL
);
"""

# Secondary indexes (the "dictionaries" from the AVL version).
# Created after the bulk insert, which is much faster than indexing row by row.
INDEXES = """
CREATE INDEX idx_residents_work       ON residents (work);
CREATE INDEX idx_residents_level      ON residents (level);
CREATE INDEX idx_residents_work_level ON residents (work, level);
"""

def generate_residents(n):
    """Yield n simulated residents as (id, work, health, family, level, money)."""
    # Pick all n jobs in one call, which is much faster than one call per resident
    jobs = random.choices(WORKS, weights=WORK_WEIGHTS, k=n)

    for i in range(1, n + 1):
        yield (
            i,
            jobs[i-1],
            random.randint(0, 100),   # health
            random.randint(0, 7),     # family size
            random.randint(1, 10),    # level
            random.randint(0, 4999),  # money
        )

def build_database(path=":memory:", n=NUM_RESIDENTS):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    with con:  # one transaction for the whole bulk insert
        con.executemany(
            "INSERT INTO residents VALUES (?, ?, ?, ?, ?, ?)",
            generate_residents(n),
        )
    con.executescript(INDEXES)
    con.execute("ANALYZE")
    return con


# ---- Query helpers (the equivalents of tree search / index lookup) ----

def find_by_id(con, resident_id):
    return con.execute(
        "SELECT * FROM residents WHERE id = ?", (resident_id,)
    ).fetchone()


def find_by_work_and_level(con, work, level):
    return con.execute(
        "SELECT * FROM residents WHERE work = ? AND level = ?", (work, level)
    ).fetchall()


def find_where(con, **filters):
    """Equality filter on any columns, e.g. find_where(con, work='medic', level=2)."""
    allowed = {"work", "health", "family", "level", "money"}
    bad = set(filters) - allowed
    if bad:
        raise ValueError(f"Unknown columns: {bad}")
    clause = " AND ".join(f"{col} = ?" for col in filters) or "1"
    return con.execute(
        f"SELECT * FROM residents WHERE {clause}", tuple(filters.values())
    ).fetchall()


def level_summary(con):
    return con.execute(
        """SELECT level, COUNT(*) AS population, ROUND(AVG(money)) AS avg_money
           FROM residents GROUP BY level ORDER BY level"""
    ).fetchall()


if __name__ == "__main__":
    t = time.time()
    db = build_database()
    print(f"Built {NUM_RESIDENTS:,} residents in {time.time() - t:.1f}s\n")

    print("Resident #421337:", dict(find_by_id(db, 421337)))

    t = time.time()
    engineers = find_by_work_and_level(db, "engineer", 3)
    print(f"\nEngineers on level 3: {len(engineers):,} "
          f"(query took {(time.time() - t) * 1000:.1f} ms)")
    print("First 3:", [dict(r) for r in engineers[:3]])

    print("\nPopulation by level:")
    for row in level_summary(db):
        print(f"  level {row['level']:>2}: {row['population']:>7,} people, "
              f"avg money {int(row['avg_money'])}")

    plan = db.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM residents WHERE work = 'engineer' AND level = 3"
    ).fetchall()
    print("\nQuery plan:", plan[0]["detail"])
