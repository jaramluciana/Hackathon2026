"""
HOLLOW-CORE: decision-support engine for The Hollow.

Pipeline:
  residents table -> per-level stats -> resource demand -> vulnerability score
  -> allocation strategies -> outcome metrics -> alert-driven re-optimisation
  with a plain-language explanation.

Depends on hollow_core_analytics.py (step 1). Works with any sqlite3
connection that has the `residents` table from the team's database module.
"""

from dataclasses import dataclass, field
import sqlite3

from lucianaCode import analyze_levels, NUM_LEVELS

RESOURCES = ("oxygen", "water", "food", "power")
SEVERITY = ("Normal", "Yellow", "Orange", "Red")


# ======================================================================
# Configuration: everything tunable lives here
# ======================================================================
@dataclass
class Config:
    vulnerable_threshold: float = 30           # health below this = vulnerable

    # Daily need per "demand unit" (resident + dependents). Abstract units:
    # oxygen kg, water litres, food kcal, power kWh.
    per_capita: dict = field(default_factory=lambda: {
        "oxygen": 0.84, "water": 20.0, "food": 2000.0, "power": 5.0})

    # Deeper levels are hotter/darker: demand grows (1 + factor*(level-1)).
    depth_factor: dict = field(default_factory=lambda: {
        "oxygen": 0.02, "water": 0.04, "food": 0.0, "power": 0.05})

    # Vulnerability score weights (normalised automatically)
    score_weights: dict = field(default_factory=lambda: {
        "low_health_pct": 0.30, "avg_health": 0.20,
        "shortage": 0.25, "env": 0.25})

    # Alert handling (severity names match the early warning system)
    alert_risk: dict = field(default_factory=lambda: {
        "Normal": 0.0, "Yellow": 0.4, "Orange": 0.7, "Red": 1.0})
    # Extra demand while a resource is in alert (rebuilding reserves, backups)
    alert_demand_boost: dict = field(default_factory=lambda: {
        "Normal": 1.0, "Yellow": 1.10, "Orange": 1.25, "Red": 1.50})

    # Sensor-name keyword -> resource (matches "Oxy (%)", "Light (%)")
    sensor_resource: dict = field(default_factory=lambda: {
        "oxy": "oxygen", "light": "power", "power": "power",
        "water": "water", "food": "food"})

    # How deadly a shortage of each resource is (used by the outcome metric)
    criticality: dict = field(default_factory=lambda: {
        "oxygen": 0.40, "water": 0.25, "food": 0.15, "power": 0.20})

    # Vulnerability-aware allocator
    floor_fraction: float = 0.60       # guaranteed share of demand, baseline
    critical_coverage: float = 0.50    # below this a level is "in crisis"

    # Reserves on hand (days of supply). Deep levels start with less.
    target_reserve_days: float = 3.0
    reserve_days_top: float = 3.0
    reserve_decay_per_level: float = 0.06


@dataclass
class LevelState:
    stats: object                                   # LevelStats
    reserve_days: dict                              # resource -> days on hand
    alerts: dict = field(default_factory=dict)      # resource -> severity


@dataclass
class Alert:
    level: int
    resource: str
    severity: str          # "Normal" clears the alert
    message: str = ""


@dataclass
class Plan:
    strategy: str
    allocation: dict       # level -> resource -> amount
    demand: dict
    scores: dict           # level -> {"score":..., "parts":{...}}
    metrics: dict


@dataclass
class Response:
    alert: Alert
    old_plan: Plan
    new_plan: Plan
    stale_metrics: dict    # old allocation judged against the new situation
    explanation: list

    def text(self):
        return "\n".join(self.explanation)


# ======================================================================
# Allocation primitives
# ======================================================================
def weighted_fill(amount, caps, weights):
    """
    Distribute `amount` across keys proportionally to `weights`, never giving
    a key more than caps[key]; leftover from capped keys is redistributed.
    """
    alloc = {k: 0.0 for k in caps}
    active = {k for k in caps if caps[k] > 1e-12 and weights[k] > 0}
    remaining = float(amount)
    while active and remaining > 1e-9:
        wsum = sum(weights[k] for k in active)
        share = {k: remaining * weights[k] / wsum for k in active}
        capped = [k for k in active if alloc[k] + share[k] >= caps[k] - 1e-12]
        if not capped:
            for k in active:
                alloc[k] += share[k]
            break
        for k in capped:
            remaining -= caps[k] - alloc[k]
            alloc[k] = caps[k]
            active.discard(k)
    return alloc


def _equal(supply, dem, scores, cfg):
    return weighted_fill(supply, dem, {k: 1.0 for k in dem})


def _population(supply, dem, scores, cfg):
    return weighted_fill(supply, dem, dem)          # proportional to demand


def _status_quo(supply, dem, scores, cfg):
    """Baseline: upper levels are served first (how the Directorate behaves)."""
    alloc, left = {}, supply
    for lvl in sorted(dem):
        alloc[lvl] = min(dem[lvl], left)
        left -= alloc[lvl]
    return alloc


def _vulnerability(supply, dem, scores, cfg, floor_frac):
    """
    Phase 1: guarantee a feasible minimum (floor) to every level.
             Floor = demand * (base + (1-base) * max(vulnerable share, alert risk)).
             If the floors alone exceed supply, scale them by risk.
    Phase 2: allocate what is left by risk-weighted remaining need.
    """
    floors = {l: dem[l] * floor_frac[l] for l in dem}
    w = {l: scores[l]["score"] + 1.0 for l in dem}
    if sum(floors.values()) >= supply:
        return weighted_fill(supply, floors, {l: w[l] * floors[l] for l in dem})
    alloc = dict(floors)
    left = supply - sum(floors.values())
    extra = weighted_fill(left, {l: dem[l] - floors[l] for l in dem},
                          {l: w[l] * dem[l] for l in dem})
    for l in dem:
        alloc[l] += extra[l]
    return alloc


STRATEGIES = ("equal", "population", "vulnerability", "status_quo")


# ======================================================================
# Outcome metrics
# ======================================================================
def evaluate(allocation, demand, scores, stats, critical, crit_w):
    """
    Judge an allocation.
    level_coverage = min over resources (a level is only as safe as its
    scarcest resource); used for fairness and crisis counts.
    Headline number weighted_people_unserved (lower is better) sums, per
    resource, people * unmet fraction * criticality * vulnerability weight,
    so improving any single resource shows up in the result.
    """
    level_cov, unserved = {}, 0.0
    for lvl in demand:
        covs = [min(1.0, allocation[lvl][r] / demand[lvl][r])
                if demand[lvl][r] > 0 else 1.0 for r in RESOURCES]
        level_cov[lvl] = min(covs)
        weight = 0.5 + scores[lvl]["score"] / 100
        for r, cov in zip(RESOURCES, covs):
            unserved += (stats[lvl].demand_units * (1 - cov) *
                         crit_w[r] * weight)

    xs = list(level_cov.values())
    jain = (sum(xs) ** 2) / (len(xs) * sum(x * x for x in xs)) if any(xs) else 0
    total_units = sum(stats[l].demand_units for l in stats) or 1
    res_cov = {r: sum(allocation[l][r] for l in demand) /
                  (sum(demand[l][r] for l in demand) or 1) for r in RESOURCES}
    return {
        "level_coverage": level_cov,
        "resource_coverage": res_cov,
        "avg_coverage": sum(level_cov[l] * stats[l].demand_units
                            for l in stats) / total_units,
        "worst_level": min(level_cov, key=level_cov.get),
        "worst_coverage": min(xs),
        "levels_in_crisis": sum(1 for x in xs if x < critical),
        "fairness_jain": jain,
        "weighted_people_unserved": unserved,
    }


# ======================================================================
# The engine
# ======================================================================
class HollowCore:
    def __init__(self, con, supply, config=None, strategy="vulnerability"):
        self.con = con
        self.cfg = config or Config()
        self.supply = dict(supply)          # resource -> units per day
        self.strategy = strategy
        self.levels = {}
        self.last_plan = None
        self.refresh_population()

    # ---- data ----------------------------------------------------------
    def refresh_population(self):
        stats = analyze_levels(self.con, self.cfg.vulnerable_threshold)
        for lvl, s in stats.items():
            if lvl in self.levels:
                self.levels[lvl].stats = s          # keep reserves & alerts
            else:
                days = max(0.0, self.cfg.reserve_days_top *
                           (1 - self.cfg.reserve_decay_per_level * (lvl - 1)))
                self.levels[lvl] = LevelState(s, {r: days for r in RESOURCES})

    @property
    def stats(self):
        return {l: st.stats for l, st in self.levels.items()}

    def set_supply_fraction(self, fractions):
        """Convenience for demos: supply = fraction * baseline total demand."""
        base = {r: sum(self.demand()[l][r] for l in self.levels)
                for r in RESOURCES}
        self.supply = {r: base[r] * fractions[r] for r in RESOURCES}

    # ---- demand --------------------------------------------------------
    def demand(self):
        c = self.cfg
        out = {}
        for lvl, st in self.levels.items():
            out[lvl] = {}
            for r in RESOURCES:
                base = (st.stats.demand_units * c.per_capita[r] *
                        (1 + c.depth_factor[r] * (lvl - 1)))
                out[lvl][r] = base * c.alert_demand_boost[
                    st.alerts.get(r, "Normal")]
        return out

    # ---- environmental risk -------------------------------------------
    def env_risk(self, lvl, resource=None):
        risks = [self.cfg.alert_risk[sev]
                 for r, sev in self.levels[lvl].alerts.items()
                 if resource is None or r == resource]
        p = 1.0
        for r in risks:
            p *= (1 - r)
        return 1 - p                        # combine independent risks

    # ---- vulnerability score ------------------------------------------
    def scores(self):
        c, w = self.cfg, self.cfg.score_weights
        wsum = sum(w.values())
        out = {}
        for lvl, st in self.levels.items():
            s = st.stats
            shortage = sum(max(0.0, 1 - st.reserve_days[r] /
                               c.target_reserve_days)
                           for r in RESOURCES) / len(RESOURCES)
            parts = {
                "low_health_pct": s.vulnerable_pct / 100,
                "avg_health": 1 - s.avg_health / 100,
                "shortage": shortage,
                "env": self.env_risk(lvl),
            }
            score = 100 * sum(w[k] * parts[k] for k in parts) / wsum
            out[lvl] = {"score": score, "parts": parts}
        return out

    def risk_ranking(self, scores=None):
        """Levels where a shortage would hurt most: score * people depending."""
        scores = scores or self.scores()
        rows = [(l, scores[l]["score"],
                 scores[l]["score"] / 100 * self.levels[l].stats.demand_units)
                for l in self.levels]
        return sorted(rows, key=lambda r: -r[2])   # (level, score, harm_index)

    # ---- allocation ----------------------------------------------------
    def allocate(self, strategy=None, demand=None, scores=None):
        strategy = strategy or self.strategy
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy must be one of {STRATEGIES}")
        demand = demand or self.demand()
        scores = scores or self.scores()
        c = self.cfg
        alloc = {l: {} for l in self.levels}

        for r in RESOURCES:
            dem = {l: demand[l][r] for l in self.levels}
            sup = self.supply[r]
            if strategy == "equal":
                res = _equal(sup, dem, scores, c)
            elif strategy == "population":
                res = _population(sup, dem, scores, c)
            elif strategy == "status_quo":
                res = _status_quo(sup, dem, scores, c)
            else:
                floor = {}
                for l in self.levels:
                    share = max(self.levels[l].stats.vulnerable_pct / 100,
                                self.env_risk(l, r))
                    floor[l] = min(1.0, c.floor_fraction +
                                   (1 - c.floor_fraction) * share)
                res = _vulnerability(sup, dem, scores, c, floor)
            for l in self.levels:
                alloc[l][r] = res[l]

        metrics = evaluate(alloc, demand, scores, self.stats,
                           c.critical_coverage, c.criticality)
        return Plan(strategy, alloc, demand, scores, metrics)

    def compare_strategies(self):
        demand, scores = self.demand(), self.scores()
        return {s: self.allocate(s, demand, scores) for s in STRATEGIES}

    # ---- alert response -----------------------------------------------
    def respond_to_alert(self, alert):
        """
        1 receive alert  2 identify level  3 update environmental risk
        4 recalc demand  5 re-run optimiser  6 explain what changed and why
        """
        if alert.resource not in RESOURCES:
            raise ValueError(f"unknown resource {alert.resource!r}")
        if alert.severity not in SEVERITY:
            raise ValueError(f"unknown severity {alert.severity!r}")
        if self.last_plan is None:
            self.last_plan = self.allocate()
        old = self.last_plan
        lvl, res = alert.level, alert.resource
        st = self.levels[lvl]

        prev_sev = st.alerts.get(res, "Normal")
        prev_risk = self.env_risk(lvl)
        old_rank = {l: i + 1 for i, (l, _, _) in
                    enumerate(self.risk_ranking(old.scores))}

        # steps 2-3: update the affected level's environmental risk
        if alert.severity == "Normal":
            st.alerts.pop(res, None)
        else:
            st.alerts[res] = alert.severity
        new_risk = self.env_risk(lvl)

        # step 4: recalculated demand and scores
        demand, scores = self.demand(), self.scores()
        stale = evaluate(old.allocation, demand, scores, self.stats,
                         self.cfg.critical_coverage, self.cfg.criticality)

        # step 5: re-run optimiser
        new = self.allocate(self.strategy, demand, scores)
        self.last_plan = new
        new_rank = {l: i + 1 for i, (l, _, _) in
                    enumerate(self.risk_ranking(scores))}

        # step 6: explanation
        L = []
        L.append(f"ALERT: Level {lvl} {res} {prev_sev} -> {alert.severity}"
                 + (f" ({alert.message})" if alert.message else ""))
        L.append(f"1. Environmental risk on level {lvl}: "
                 f"{prev_risk:.2f} -> {new_risk:.2f}.")
        L.append(f"2. Vulnerability score: {old.scores[lvl]['score']:.1f} -> "
                 f"{scores[lvl]['score']:.1f}; risk rank "
                 f"#{old_rank[lvl]} -> #{new_rank[lvl]} of {len(self.levels)}.")
        d0, d1 = old.demand[lvl][res], demand[lvl][res]
        if d0:
            L.append(f"3. {res.capitalize()} demand on level {lvl}: "
                     f"{d0:,.0f} -> {d1:,.0f} ({(d1 / d0 - 1) * 100:+.0f}%), "
                     f"to rebuild reserves during the alert.")
        a0, a1 = old.allocation[lvl][res], new.allocation[lvl][res]
        c0 = min(1, a0 / d1) if d1 else 1
        c1 = min(1, a1 / d1) if d1 else 1
        L.append(f"4. {self.strategy} optimiser re-run. {res.capitalize()} to "
                 f"level {lvl}: {a0:,.0f} -> {a1:,.0f} "
                 f"({(a1 / a0 - 1) * 100 if a0 else 0:+.1f}%); coverage of "
                 f"new demand {c0 * 100:.0f}% (stale plan) -> {c1 * 100:.0f}%.")

        donors = sorted(
            ((l, new.allocation[l][res] - old.allocation[l][res])
             for l in self.levels if l != lvl), key=lambda x: x[1])
        donors = [(l, d) for l, d in donors if d < -1e-6][:3]
        if donors:
            L.append(f"5. Supply of {res} is fixed, so this was funded by "
                     + ", ".join(f"level {l} ({d:,.0f})" for l, d in donors)
                     + ".")
        elif a1 - a0 > 1e-6:
            L.append(f"5. Spare {res} supply existed, so no other level "
                     f"lost anything.")
        if c1 < 1:
            L.append(f"   WARNING: level {lvl} {res} is still only "
                     f"{c1 * 100:.0f}% covered; total supply is the "
                     f"bottleneck. Consider emergency stock or rationing.")

        u_stale, u_new = (stale["weighted_people_unserved"],
                          new.metrics["weighted_people_unserved"])
        gain = (u_stale - u_new) / u_stale * 100 if u_stale else 0
        L.append(f"6. Outcome: weighted people unserved "
                 f"{u_stale:,.0f} (keep old plan) -> {u_new:,.0f} "
                 f"(re-optimised): {gain:+.1f}% improvement. "
                 f"Levels in crisis: {stale['levels_in_crisis']} -> "
                 f"{new.metrics['levels_in_crisis']}.")
        return Response(alert, old, new, stale, L)


# ======================================================================
# Bridge to the early warning system (no changes to teammate's code needed)
# ======================================================================
def severity_from_ratio(ratio):
    """Same thresholds as the teammate's alert_level()."""
    if ratio <= 0:
        return "Red"
    if ratio <= 10:
        return "Orange"
    if ratio <= 20:
        return "Yellow"
    return "Normal"


class SensorBridge:
    """
    Call poll(level, sensor) every tick with the teammate's Sensor objects.
    When a sensor's severity changes, HOLLOW-CORE is re-run and the Response
    is returned (otherwise None).
    """
    def __init__(self, core):
        self.core = core
        self._last = {}

    def _resource(self, sensor_name):
        n = sensor_name.lower()
        for key, res in self.core.cfg.sensor_resource.items():
            if key in n:
                return res
        raise ValueError(f"Don't know which resource sensor {sensor_name!r} is")

    def poll(self, level, sensor):
        ratio = sensor.remaining_ratio()
        sev = severity_from_ratio(ratio)
        key = (level, sensor.name)
        if sev == self._last.get(key, "Normal"):
            return None
        self._last[key] = sev
        return self.core.respond_to_alert(
            Alert(level, self._resource(sensor.name), sev,
                  f"{sensor.name} at {ratio:.1f}%"))


# ======================================================================
# Demo
# ======================================================================
def _demo_db(n=100_000):
    try:
        from hollow_db import build_database      # teammate's module
        return build_database(n=n)
    except ImportError:
        import random
        con = sqlite3.connect(":memory:")
        con.execute("""CREATE TABLE residents (id INTEGER PRIMARY KEY,
            work TEXT, health INTEGER, family INTEGER, level INTEGER,
            money INTEGER)""")
        # deeper levels are sicker, as in the story
        rows = []
        for i in range(1, n + 1):
            lvl = random.randint(1, 10)
            rows.append((i, "miner", max(0, min(100, int(
                random.gauss(75 - 4 * lvl, 20)))), random.randint(0, 7),
                         lvl, random.randint(0, 4999)))
        con.executemany("INSERT INTO residents VALUES (?,?,?,?,?,?)", rows)
        con.execute("CREATE INDEX idx_residents_level ON residents (level)")
        return con


class _DemoSensor:                       # stand-in with the same interface
    def __init__(self, name, ratio):
        self.name, self.ratio = name, ratio

    def remaining_ratio(self):
        return self.ratio


def _print_comparison(plans):
    print(f"{'strategy':<14}{'avg cov':>8}{'worst lvl':>10}{'worst cov':>10}"
          f"{'crisis':>7}{'fairness':>9}{'unserved':>11}")
    for name, p in plans.items():
        m = p.metrics
        print(f"{name:<14}{m['avg_coverage'] * 100:>7.1f}%"
              f"{m['worst_level']:>10}{m['worst_coverage'] * 100:>9.1f}%"
              f"{m['levels_in_crisis']:>7}{m['fairness_jain']:>9.3f}"
              f"{m['weighted_people_unserved']:>11,.0f}")


if __name__ == "__main__":
    core = HollowCore(_demo_db(), supply={r: 0 for r in RESOURCES})
    core.set_supply_fraction(
        {"oxygen": 0.85, "water": 0.80, "food": 0.75, "power": 0.70})

    print("== Where would shortages hurt most? ==")
    for lvl, score, harm in core.risk_ranking()[:5]:
        print(f"  level {lvl:>2}: vulnerability {score:5.1f}, "
              f"harm index {harm:,.0f}")

    print("\n== Strategy comparison (no emergency) ==")
    _print_comparison(core.compare_strategies())

    print("\n== Early warning feed -> optimiser ==")
    bridge = SensorBridge(core)
    oxy9 = _DemoSensor("Oxy (%)", 55)
    bridge.poll(9, oxy9)                                   # Normal, no event
    for ratio in (18, 8):                                  # Yellow, Orange
        oxy9.ratio = ratio
        resp = bridge.poll(9, oxy9)
        print("\n" + resp.text())
