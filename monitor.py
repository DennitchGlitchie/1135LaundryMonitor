import pigpio
import time
from collections import deque

PIN = 17
pulse_times = deque()

pi = pigpio.pi()
if not pi.connected:
    raise RuntimeError("Cannot connect to pigpio daemon")

def count_pulse(gpio, level, tick):
    now = time.time()
    pulse_times.append(now)

pi.set_mode(PIN, pigpio.INPUT)
cb = pi.callback(PIN, pigpio.RISING_EDGE, count_pulse)

# Constants
PULSES_PER_ROTATION = 20
MPS_PER_ROTATION = 1.75
PULSE_TO_MPS = MPS_PER_ROTATION / PULSES_PER_ROTATION
MPS_TO_MPH = 2.23694

def calculate_wind_speed(pulses, interval_seconds):
    if interval_seconds == 0:
        return 0.0, 0.0
    wind_mps = (pulses / interval_seconds) * PULSE_TO_MPS
    wind_mph = wind_mps * MPS_TO_MPH
    return wind_mps, wind_mph

def count_recent_pulses(window_seconds):
    now = time.time()
    while pulse_times and pulse_times[0] < now - 60:
        pulse_times.popleft()
    return len([t for t in pulse_times if t >= now - window_seconds])

print("Counting pulses with pigpio. Press Ctrl+C to stop.\n")

try:
    while True:
        time.sleep(1)
        print(f"{'Time Window':>12} | {'Pulses':>6} | {'m/s':>6} | {'mph':>6}")
        print("-" * 40)
        for window in [1, 5, 10, 30, 60]:
            pulses = count_recent_pulses(window)
            wind_mps, wind_mph = calculate_wind_speed(pulses, window)
            print(f"{window:>12}s | {pulses:>6} | {wind_mps:>6.2f} | {wind_mph:>6.2f}")
        print("-" * 40)
except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    cb.cancel()
    pi.stop()
