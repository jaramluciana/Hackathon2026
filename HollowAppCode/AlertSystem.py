import random
import time
from collections import deque


# ---------- Sensor ----------
class Sensor:
    """Simulated sensor: value drops over time with some noise."""

    def __init__(self, name, value, drain_per_sec, danger_level):
        self.name = name
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


# ---------- Main program ----------
def main():
    sensors = [
        Sensor("Light (%)", 100, 1.0, 0),
        Sensor("Oxy (%)", 21, 0.1, 16),
    ]
    t = 0

    # Print the 100% mark once at the start
    for s in sensors:
        print(f"[t=  0] {s.name:9s} = {s.value:6.2f} (100.0%) | left    -- | Normal")

    while True:
        if all(s.depleted for s in sensors):
            print("\n[SYSTEM SHUTDOWN] ALL RESOURCES DEPLETED. PROGRAM TERMINATED.")
            break

        for s in sensors:
            if s.depleted:
                continue

            s.read(t)
            left = s.time_left()
            ratio = s.remaining_ratio()
            level = alert_level(ratio)

            # Normal level: print once at 70% and 50%, nothing else
            if level == "Normal":
                for mark in (70, 50):
                    if ratio <= mark and mark not in s.printed_marks:
                        s.printed_marks.add(mark)
                        txt = f"{left:.0f}s" if left is not None else "--"
                        print(f"[t={t:3d}] {s.name:9s} = {s.value:6.2f} ({ratio:5.1f}%) | left {txt:>5} | Normal")
                continue

            txt = f"{max(0, left):.0f}s" if left is not None else "--"
            print(f"[t={t:3d}] {s.name:9s} = {s.value:6.2f} ({ratio:5.1f}%) | left {txt:>5} | {level}")

            if level == "Yellow" and not s.warned_yellow:
                warning_msg = f"[YELLOW ALERT] {s.name} IS AT 20% OR BELOW!"
                print(f">>> {warning_msg}")
                s.warned_yellow = True
            elif level == "Orange" and not s.warned_orange:
                warning_msg = f"[ORANGE ALERT] {s.name} IS AT 10% OR BELOW!"
                print(f">>> {warning_msg}")
                s.warned_orange = True

            if left is not None and left <= 0:
                resource_label = "LIGHT BATTERY" if "Light" in s.name else "OXYGEN"
                warning_msg = f"WARNING: {resource_label} DEPLETED! CRITICAL LEVEL REACHED!"
                print("\n" + (warning_msg + "\n") * 3)
                s.depleted = True

        t += 1
        time.sleep(0.5)


if __name__ == "__main__":
    main()