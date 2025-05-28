import pigpio
import time
import json
import datetime
from collections import deque

PIN = 17
LOG_FILE = "/home/garges/WindMonitor/wind_log.jsonl"

PULSES_PER_ROTATION = 20
MPS_PER_ROTATION = 1.75
PULSE_TO_MPS = MPS_PER_ROTATION / PULSES_PER_ROTATION
MPS_TO_MPH = 2.23694

# Counter for pulses in current second
pulse_count = 0

def count_pulse(gpio, level, tick):
    """Callback for each pulse - increment counter"""
    global pulse_count
    pulse_count += 1

def calculate_wind_speed(pulses_per_second):
    """Calculate wind speed from pulses per second"""
    wind_mps = pulses_per_second * PULSE_TO_MPS
    wind_mph = wind_mps * MPS_TO_MPH
    return wind_mps, wind_mph

def main():
    global pulse_count
    
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("Cannot connect to pigpio daemon")

    pi.set_mode(PIN, pigpio.INPUT)
    cb = pi.callback(PIN, pigpio.RISING_EDGE, count_pulse)

    try:
        with open(LOG_FILE, "a") as f:
            while True:
                time.sleep(1)
                
                # Get pulse count for this second and reset counter
                current_pulses = pulse_count
                pulse_count = 0
                
                # Calculate wind speed for this second
                mps, mph = calculate_wind_speed(current_pulses)
                
                record = {
                    "timestamp": time.time(),
                    "time_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "pulses": current_pulses,
                    "mps": round(mps, 2),
                    "mph": round(mph, 2)
                }
                f.write(json.dumps(record) + "\n")
                f.flush()
                
    finally:
        cb.cancel()
        pi.stop()

if __name__ == "__main__":
    main()
