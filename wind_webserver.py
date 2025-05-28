import json
import time
from collections import deque
from flask import Flask, render_template_string, jsonify, send_from_directory, url_for
import threading
import datetime
import os

app = Flask(__name__, 
            static_folder='/home/garges/WindMonitor/static',
            static_url_path='/static')

# Create static directory if needed
os.makedirs('/home/garges/WindMonitor/static', exist_ok=True)

# Configuration
LOG_FILE = "/home/garges/WindMonitor/wind_log.jsonl"
TIME_WINDOWS = [1, 5, 10, 30, 60]
GRAPH_HISTORY_MINUTES = 60

# Wind calculation constants
PULSES_PER_ROTATION = 20
MPS_PER_ROTATION = 1.75
PULSE_TO_MPS = MPS_PER_ROTATION / PULSES_PER_ROTATION
MPS_TO_MPH = 2.23694

# Keep up to 3 days of data in memory (4320 minutes)
MAX_HISTORY_MINUTES = 4320

# Global data storage - store log entries (one per second)
log_entries = deque()  # Each entry has timestamp, pulses count, etc.
current_data = {f"{w}s": {"pulses": 0, "mps": 0.0, "mph": 0.0} for w in TIME_WINDOWS}
current_data["last_updated"] = ""
history_data = {f"{w}s": [] for w in TIME_WINDOWS}

def calculate_wind_speed_from_pulse_rate(pulses_per_second):
    """Calculate wind speed from pulses per second"""
    wind_mps = pulses_per_second * PULSE_TO_MPS
    wind_mph = wind_mps * MPS_TO_MPH
    return wind_mps, wind_mph

def read_log_file():
    """Read and parse the log file, returning new entries since last read"""
    try:
        if not os.path.exists(LOG_FILE):
            return []
        
        new_entries = []
        last_known_timestamp = log_entries[-1]['timestamp'] if log_entries else 0
        
        with open(LOG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        # Only add if we haven't seen this timestamp before
                        if entry['timestamp'] > last_known_timestamp:
                            new_entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        return new_entries
    except Exception as e:
        print(f"Error reading log file: {e}")
        return []

def calculate_window_data(window_seconds):
    """Calculate wind data for a specific time window by summing recent entries"""
    if not log_entries:
        return {"pulses": 0, "mps": 0.0, "mph": 0.0}
    
    # Get the last N entries (one per second)
    entries_needed = min(window_seconds, len(log_entries))
    recent_entries = list(log_entries)[-entries_needed:]
    
    if not recent_entries:
        return {"pulses": 0, "mps": 0.0, "mph": 0.0}
    
    # Sum up pulses from recent entries
    total_pulses = sum(entry['pulses'] for entry in recent_entries)
    
    # Calculate average pulses per second over the window
    pulses_per_second = total_pulses / window_seconds
    
    # Calculate wind speed
    mps, mph = calculate_wind_speed_from_pulse_rate(pulses_per_second)
    
    return {
        "pulses": total_pulses,
        "mps": round(mps, 2),
        "mph": round(mph, 2)
    }

def generate_history_data():
    """Generate history data for charts using proper sliding window calculations"""
    if not log_entries:
        return
    
    # Convert log_entries to list for easier indexing
    entries_list = list(log_entries)
    
    for window_seconds in TIME_WINDOWS:
        window_key = f"{window_seconds}s"
        history_points = []
        
        # For each entry, calculate the wind speed for that time using the sliding window
        for i in range(len(entries_list)):
            # Get entries for the sliding window ending at this point
            start_idx = max(0, i - window_seconds + 1)
            window_entries = entries_list[start_idx:i+1]
            
            if len(window_entries) >= window_seconds or i >= len(entries_list) - window_seconds:
                # Sum pulses in the window
                total_pulses = sum(entry['pulses'] for entry in window_entries)
                # Calculate average pulses per second
                actual_window_size = len(window_entries)
                pulses_per_second = total_pulses / actual_window_size if actual_window_size > 0 else 0
                # Calculate wind speed
                mps, mph = calculate_wind_speed_from_pulse_rate(pulses_per_second)
                
                entry = entries_list[i]
                time_str = entry['time_str'].split()[1]  # Just time, not date
                
                history_points.append({
                    "timestamp": entry['timestamp'],
                    "time_str": time_str,
                    "mph": round(mph, 2)
                })
        
        # For performance, thin out the history data if we have too many points
        if len(history_points) > 1000:
            # Keep every Nth point to reduce to about 500 points
            step = len(history_points) // 500
            history_points = history_points[::step]
        
        history_data[window_key] = history_points

def update_data_from_log():
    """Continuously read log file and update current/history data"""
    last_file_size = 0
    
    while True:
        try:
            # Check if file has grown (new data available)
            if os.path.exists(LOG_FILE):
                current_size = os.path.getsize(LOG_FILE)
                if current_size != last_file_size:
                    # Read new entries
                    new_entries = read_log_file()
                    
                    # Add new entries to our deque
                    for entry in new_entries:
                        log_entries.append(entry)
                    
                    # Prune old data (keep last MAX_HISTORY_MINUTES worth of seconds)
                    max_entries = MAX_HISTORY_MINUTES * 60
                    while len(log_entries) > max_entries:
                        log_entries.popleft()
                    
                    # Update current data for all time windows
                    for window in TIME_WINDOWS:
                        window_key = f"{window}s"
                        current_data[window_key] = calculate_window_data(window)
                    
                    # Update history data
                    generate_history_data()
                    
                    # Update last_updated timestamp
                    if log_entries:
                        current_data["last_updated"] = log_entries[-1]['time_str']
                    
                    last_file_size = current_size
            
        except Exception as e:
            print(f"Error updating data from log: {e}")
        
        time.sleep(1)  # Check for updates every second

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>1135 Wind Monitor</title>
    <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='wind_favicon-32x32_V2.png') }}">
    <link rel="shortcut icon" href="{{ url_for('static', filename='wind_favicon-32x32_V2.png') }}">
    <link rel="apple-touch-icon" sizes="32x32" href="{{ url_for('static', filename='wind_favicon-32x32_V2.png') }}">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-top: 0; text-align: center; }
        h2 { color: #2c3e50; }
        .subtitle { text-align: center; color: #7f8c8d; margin-top: -10px; margin-bottom: 20px; }
        .card { margin-bottom: 20px; padding: 15px; border-radius: 4px; background-color: #f9f9f9; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: right; border-bottom: 1px solid #ddd; }
        th:first-child, td:first-child { text-align: left; }
        th { background-color: #f2f2f2; }
        .wind-gauge { text-align: center; font-size: 28px; font-weight: bold; margin: 20px 0; }
        .chart-container { height: 300px; margin-top: 20px; }
        .last-updated { text-align: right; color: #7f8c8d; font-size: 0.8em; margin-top: 10px; }
        .settings { margin: 10px 0; padding: 10px; background-color: #f2f2f2; border-radius: 4px; }
        .settings label { margin-right: 10px; }
        .settings input { width: 60px; padding: 4px; margin-right: 20px; }
        .settings button { background-color: #2980b9; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; }
        .settings button:hover { background-color: #3498db; }
        .roof-gif { text-align: center; margin: 20px 0; }
        .roof-gif img { max-width: 100%; border-radius: 4px; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script>
</head>
<body>
    <div class="container">
        <h1>The Wind Speed at 1135 Masonic is:</h1>
        <p class="subtitle">(there is a cute little anemometer spinning on the roof - see if you can spot it!)</p>
        
        <div class="card">
            <div class="wind-gauge"><span id="current-wind">0.00</span> mph</div>
            <div class="last-updated">Last updated: <span id="last-updated">Never</span></div>
        </div>
        
        <div class="card">
            <h2>Current Readings</h2>
            <table>
                <thead><tr><th>Time Window</th><th>Pulses</th><th>m/s</th><th>mph</th></tr></thead>
                <tbody id="readings-table"><tr><td>Loading...</td><td></td><td></td><td></td></tr></tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>Wind Speed History</h2>
            <div class="settings">
                <label for="historyMinutes">History (minutes):</label>
                <input type="number" id="historyMinutes" min="1" max="4320" value="{{ graph_history_minutes }}">
                <button id="updateHistory">Update</button>
            </div>
            <div class="chart-container"><canvas id="windChart"></canvas></div>
        </div>
        
        <div class="roof-gif"><img src="{{ url_for('static', filename='roof_gif.gif') }}" alt="Roof with anemometer"></div>
    </div>

    <script>
        let windChart;
        const TIME_WINDOWS = {{ time_windows|safe }}.map(w => w + "s");
        let graphHistoryMinutes = {{ graph_history_minutes }};
        
        const colors = ['#2980b9', '#27ae60', '#f39c12', '#8e44ad', '#e74c3c', '#16a085', '#d35400', '#2c3e50', '#7f8c8d', '#c0392b'];
        
        function updateCurrentData() {
            fetch('/api/current')
                .then(r => r.json())
                .then(data => {
                    const mainWindow = data['10s'] || data[Object.keys(data).find(k => k.endsWith('s'))];
                    if (mainWindow) document.getElementById('current-wind').textContent = mainWindow.mph.toFixed(2);
                    
                    document.getElementById('last-updated').textContent = data.last_updated;
                    
                    const windowKeys = Object.keys(data).filter(k => k.endsWith('s')).sort((a, b) => parseInt(a) - parseInt(b));
                    document.getElementById('readings-table').innerHTML = windowKeys.map(w => 
                        `<tr><td>${w}</td><td>${data[w].pulses}</td><td>${data[w].mps.toFixed(2)}</td><td>${data[w].mph.toFixed(2)}</td></tr>`
                    ).join('');
                })
                .catch(console.error);
        }
        
        function updateHistoryChart() {
            fetch('/api/history')
                .then(r => r.json())
                .then(data => {
                    const windowsToPlot = ['1s', '10s', '30s'];
                    const now = Date.now() / 1000;
                    const cutoffTime = now - (graphHistoryMinutes * 60);
                    
                    const datasets = windowsToPlot.map((windowKey, i) => {
                        const windowData = data[windowKey] || [];
                        const filteredData = windowData.filter(e => e.timestamp >= cutoffTime);
                        const label = `${windowKey} Wind Speed`;
                        
                        return {
                            label: label,
                            data: filteredData.map(item => ({ x: item.time_str, y: item.mph })),
                            borderColor: colors[i],
                            backgroundColor: `${colors[i]}33`,
                            tension: 0.3,
                            fill: false,
                            pointRadius: filteredData.length > 100 ? 0 : 2
                        };
                    }).filter(d => d.data.length > 0);
                    
                    if (!datasets.length) return;
                    
                    const labels = datasets.reduce((longest, d) => d.data.length > longest.length ? d.data : longest, []).map(item => item.x);
                    
                    if (windChart) {
                        windChart.data.labels = labels;
                        
                        datasets.forEach((newDataset, i) => {
                            if (windChart.data.datasets[i]) {
                                windChart.data.datasets[i].data = newDataset.data;
                            } else {
                                windChart.data.datasets.push(newDataset);
                            }
                        });
                        
                        if (windChart.data.datasets.length > datasets.length) {
                            windChart.data.datasets.splice(datasets.length);
                        }
                        
                        windChart.update('none');
                    } else {
                        const ctx = document.getElementById('windChart').getContext('2d');
                        windChart = new Chart(ctx, {
                            type: 'line',
                            data: { labels, datasets },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: { mode: 'index', intersect: false },
                                scales: {
                                    y: { beginAtZero: true, title: { display: true, text: 'Wind Speed (mph)' }},
                                    x: { title: { display: true, text: 'Time' }}
                                }
                            }
                        });
                    }
                })
                .catch(console.error);
        }
        
        document.getElementById('updateHistory').addEventListener('click', function() {
            const value = parseInt(document.getElementById('historyMinutes').value);
            if (value >= 1 && value <= 4320) {
                graphHistoryMinutes = value;
                updateHistoryChart();
            } else {
                alert('Please enter a value between 1 and 4320 minutes.');
                document.getElementById('historyMinutes').value = graphHistoryMinutes;
            }
        });
        
        updateCurrentData();
        updateHistoryChart();
        setInterval(updateCurrentData, 1000);
        setInterval(updateHistoryChart, 5000);
    </script>
</body>
</html>'''

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'wind_favicon-32x32_V2.png', mimetype='image/png')

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                time_windows=TIME_WINDOWS,
                                graph_history_minutes=GRAPH_HISTORY_MINUTES)

@app.route('/api/current')
def get_current_data():
    return jsonify(current_data)

@app.route('/api/history')
def get_history_data():
    return jsonify(history_data)

def main():
    try:
        # Start background log reading thread
        log_thread = threading.Thread(target=update_data_from_log, daemon=True)
        log_thread.start()
        
        # Check favicon file
        favicon_path = os.path.join(app.static_folder, 'wind_favicon-32x32_V2.png')
        print(f"Favicon: {'✓ Found' if os.path.exists(favicon_path) else '✗ Missing'} - {favicon_path}")
        
        # Check log file
        print(f"Log file: {'✓ Found' if os.path.exists(LOG_FILE) else '✗ Missing'} - {LOG_FILE}")
        
        print("Starting Flask server on port 5001...")
        app.run(host='0.0.0.0', port=5001, debug=False)
        
    except KeyboardInterrupt:
        print("Stopped by user.")

if __name__ == "__main__":
    main()
