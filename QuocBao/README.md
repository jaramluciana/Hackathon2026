Hollow Watch: Early Warning System

A small Python program that warns people before light or oxygen runs out, not after.

What It Does

Instead of saying "it ran out", the program says "you have X seconds left".

For each sensor it:

Reads the current value.
Predicts how much time is left.
Shows an alert level.
Alert Levels
Level	Remaining	What You See
Normal	above 20%	A message at 100%, 70% and 50% only
Yellow	20% or below	Warning message
Orange	10% or below	Warning message
Red	0%	Resource depleted
How to Run

You need Python 3. No other installs.

python AlertSystem.py

The program stops by itself when everything is depleted.

Example Output
[t=  0] Light (%) = 100.00 (100.0%) | left    -- | Normal
[t= 40] Oxy (%)   =  17.02 ( 20.4%) | left   10s | Yellow
>>> [YELLOW ALERT] Oxy (%) IS AT 20% OR BELOW!
WARNING: OXYGEN DEPLETED! CRITICAL LEVEL REACHED!
Change the Sensors

Edit this list in main():

python
sensors = [
    Sensor("Light (%)", 100, 1.0, 0),  # name, start, drop per tick, danger level
    Sensor("Oxy (%)", 21, 0.1, 16),
]
Limits
Sensor values are simulated.
Predictions assume a steady rate of decline.
Alerts appear in the terminal only.
