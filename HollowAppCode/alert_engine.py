import random
import threading
from collections import deque
from datetime import datetime


# ---------- Sensor (your original logic) ----------
class Sensor:
    """Simulated sensor: value drops over time with some noise."""

    def __init__(self, name, label, value, drain_per_sec, danger_level):
        self.name = name
        self.label = label
        self.initial_value = value
        self.value = value
        self.drain = drain_per_sec
        self.danger = danger_level
        self.history = deque(maxlen=10)
        self.depleted = False
        self.warned_yellow = False
        self.warned_orange = False
        self.printed_marks = set()

    def read(self, t):
        self.value -= self.drain + random.uniform(-0.05, 0.05)
        self.history.append((t, self.value))
        return self.value

    def time_left(self):
        if self.value <= self.danger:
            return 0.0
        if len(self.history) < 2:
            return None
        (t0, v0), (t1, v1) = self.history[0], self.history[-1]
        rate = (v0 - v1) / (t1 - t0)
        if rate <= 0:
            return None
        return (v1 - self.danger) / rate

    def remaining_ratio(self):
        usable_range = self.initial_value - self.danger
        if usable_range <= 0:
            return 0.0
        current_usable = max(0.0, self.value - self.danger)
        return (current_usable / usable_range) * 100


def alert_level(ratio):
    if ratio <= 0:
        return "Red"
    if ratio <= 10:
        return "Orange"
    if ratio <= 20:
        return "Yellow"
    return "Normal"


# ---------- Engine ----------
# Level 1 = most battery, level 10 = least battery
LEVEL_CONFIG = {
    lv: dict(
        light=100 - (lv - 1) * 9,                  # 100, 91, 82 ... 19
        light_drain=1.0,
        oxy=21,
        oxy_drain=round(0.10 + (lv - 1) * 0.03, 2),  # 0.10 ... 0.37
    )
    for lv in range(1, 11)
}

class AlertEngine:
    """Runs the simulation in a background thread and notifies listeners.

    Listeners are functions: callback(kind, data)
      kind == "tick"  -> sensors were updated
      kind == "alert" -> a new notification was created (data = dict)
    """

    def __init__(self):
        self.listeners = []
        self.notifications = []      # newest first
        self._thread = None
        self._stop = threading.Event()
        self.level = 1               # default level before anyone logs in
        self.reset()

    # --- state ---
    def reset(self):
        cfg = LEVEL_CONFIG[self.level]
        # sensors[0] = light of the logged-in level
        # sensors[1:] = oxygen of level 1..10 (index i -> level i)
        self.sensors = [
            Sensor("Light (%)", f"LIGHT BATTERY (LEVEL {self.level})",
                   cfg["light"], cfg["light_drain"], 0)
        ]
        for lv in range(1, 11):
            c = LEVEL_CONFIG[lv]
            self.sensors.append(
                Sensor(f"Oxy L{lv}", f"OXYGEN OF LEVEL {lv}",
                       c["oxy"], c["oxy_drain"], 16)
            )
        self.t = 0

    def set_level(self, level):
        """Logged-in level changed: replace the light sensor, then report
        the current state of this level's oxygen."""
        if level == self.level:
            return
        self.stop()
        self.level = level
        cfg = LEVEL_CONFIG[level]
        self.sensors[0] = Sensor(
            "Light (%)", f"LIGHT BATTERY (LEVEL {level})",
            cfg["light"], cfg["light_drain"], 0)

        oxy = self.sensors[level]
        if oxy.depleted:
            self.notify("Red", f"WARNING: {oxy.label} DEPLETED! "
                               "CRITICAL LEVEL REACHED!")
        self.start()

    # --- listeners ---
    def subscribe(self, callback):
        if callback not in self.listeners:
            self.listeners.append(callback)

    def unsubscribe(self, callback):
        if callback in self.listeners:
            self.listeners.remove(callback)

    def _emit(self, kind, data=None):
        for cb in list(self.listeners):
            try:
                cb(kind, data)
            except Exception as ex:
                print("Listener error:", ex)

    # --- notifications ---
    def notify(self, level, text, popup=True):
        n = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "text": text,
            "read": False,
            "popup": popup,
        }
        self.notifications.insert(0, n)
        self._emit("alert", n)

    def unread_count(self):
        return sum(1 for n in self.notifications if not n["read"])

    def mark_all_read(self):
        for n in self.notifications:
            n["read"] = True

    # --- control ---
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)

    def restart(self):
        self.stop()
        self.reset()
        self.start()

    def shutdown(self):
        """Call on logout: stop everything and forget all notifications."""
        self.stop()
        self.reset()
        self.notifications.clear()

    def _run(self):
        while not self._stop.is_set():
            mine = [self.sensors[0], self.sensors[self.level]]
            if all(s.depleted for s in mine):
                self.notify("Red", "ALL RESOURCES DEPLETED. SYSTEM SHUTDOWN.")
                self._emit("tick")
                break

            for idx, s in enumerate(self.sensors):
                if s.depleted:
                    continue

                s.read(self.t)
                left = s.time_left()

                # Other levels keep running silently: no alert, no banner
                if idx != 0 and idx != self.level:
                    if left is not None and left <= 0:
                        s.depleted = True
                    continue

                ratio = s.remaining_ratio()
                level = alert_level(ratio)

                if level == "Normal":
                    for mark in (70, 50):
                        if ratio <= mark and mark not in s.printed_marks:
                            s.printed_marks.add(mark)
                            self.notify("Info", f"{s.label} is at {mark}%",
                                        popup=False)

                elif level == "Yellow" and not s.warned_yellow:
                    s.warned_yellow = True
                    self.notify("Yellow",
                                f"{s.label}: ONLY {ratio:.0f}% LEFT!")

                elif level == "Orange" and not s.warned_orange:
                    s.warned_orange = True
                    self.notify("Orange",
                                f"{s.label}: ONLY {ratio:.0f}% LEFT!")

                if left is not None and left <= 0:
                    s.depleted = True
                    self.notify(
                        "Red",
                        f"WARNING: {s.label} DEPLETED! CRITICAL LEVEL REACHED!",
                    )

            self._emit("tick")
            self.t += 1
            self._stop.wait(0.5)


# One shared engine for the whole app
engine = AlertEngine()