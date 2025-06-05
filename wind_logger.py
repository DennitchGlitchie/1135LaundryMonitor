import pigpio
import time
import csv
import datetime
import os
from collections import deque

PIN = 17
LOG_FILE = "/home/garges/WindMonitor/wind_log.csv"

PULSES_PER_ROTATION = 20
MPS_PER_ROTATION = 1.75
PULSE_TO_MPS = MPS_PER_ROTATION / PULSES_PER_ROTATION
MPS_TO_MPH = 2.23694

# Time windows in seconds
TIME_WINDOWS = [1, 5, 10, 30, 60]

# Keep track of pulse counts for each second (need 60 seconds max)
pulse_history = deque(maxlen=60)

# Counter for pulses in current second
pulse_count = 0

def count_pulse(gpio, level, tick):
    """Callback for each pulse - increment counter"""
    global pulse_count
    pulse_count += 1

def calculate_wind_speed_from_pulses(total_pulses, time_seconds):
    """Calculate wind speed from total pulses over time period"""
    if time_seconds == 0:
        return 0.0
    
    pulses_per_second = total_pulses / time_seconds
    wind_mps = pulses_per_second * PULSE_TO_MPS
    wind_mph = wind_mps * MPS_TO_MPH
    return round(wind_mph, 2)

def calculate_window_speeds():
    """Calculate wind speeds for all time windows"""
    speeds = {}
    
    for window in TIME_WINDOWS:
        if len(pulse_history) >= window:
            # Sum pulses from the last 'window' seconds
            total_pulses = sum(list(pulse_history)[-window:])
            speeds[window] = calculate_wind_speed_from_pulses(total_pulses, window)
        else:
            # Not enough data yet
            speeds[window] = None
    
    return speeds

def initialize_csv():
    """Create CSV file with headers if it doesn't exist"""
    try:
        # Check if file exists and has content
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                first_line = f.readline().strip()
                # Check if first line looks like headers (contains 'time')
                if first_line and 'time' in first_line:
                    print(f"CSV file already exists with headers: {LOG_FILE}")
                    return
                else:
                    print(f"CSV file exists but missing headers, backing up and recreating: {LOG_FILE}")
                    # Backup the existing file
                    backup_name = LOG_FILE.replace('.csv', '_backup.csv')
                    os.rename(LOG_FILE, backup_name)
        
        # Create new file with headers
        with open(LOG_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            headers = ['time'] + [str(w) for w in TIME_WINDOWS]
            writer.writerow(headers)
        print(f"Created new CSV file with headers: {LOG_FILE}")
        
    except Exception as e:
        print(f"Error initializing CSV file: {e}")
        raise

def main():
    global pulse_count
    
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("Cannot connect to pigpio daemon")

    pi.set_mode(PIN, pigpio.INPUT)
    cb = pi.callback(PIN, pigpio.RISING_EDGE, count_pulse)

    # Initialize CSV file
    initialize_csv()

    try:
        with open(LOG_FILE, "a", newline='') as f:
            writer = csv.writer(f)
            
            print("Starting wind monitoring...")
            print(f"Time windows: {TIME_WINDOWS} seconds")
            print(f"Logging to: {LOG_FILE}")
            
            while True:
                time.sleep(1)
                
                # Get pulse count for this second and reset counter
                current_pulses = pulse_count
                pulse_count = 0
                
                # Add to history
                pulse_history.append(current_pulses)
                
                # Calculate wind speeds for all windows
                window_speeds = calculate_window_speeds()
                
                # Prepare CSV row
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [timestamp]
                
                for window in TIME_WINDOWS:
                    speed = window_speeds[window]
                    row.append(speed if speed is not None else '')
                
                # Write to CSV
                writer.writerow(row)
                f.flush()
                
                # Print current status (optional - remove if too verbose)
                valid_speeds = {k: v for k, v in window_speeds.items() if v is not None}
                if valid_speeds:
                    speed_str = ", ".join([f"{k}s: {v}mph" for k, v in valid_speeds.items()])
                    print(f"{timestamp} - {speed_str}")
                
    except KeyboardInterrupt:
        print("\nStopping wind monitor...")
    finally:
        cb.cancel()
        pi.stop()

if __name__ == "__main__":
    main()
