import csv
import time
import os
from collections import deque
from flask import Flask, render_template_string, jsonify, send_from_directory, url_for, request
import threading
import datetime

app = Flask(__name__, 
            static_folder='/home/garges/WindMonitor/static',
            static_url_path='/static')

# Create static directory if needed
os.makedirs('/home/garges/WindMonitor/static', exist_ok=True)

# Configuration
LOG_FILE = "/home/garges/WindMonitor/wind_log.csv"
TIME_WINDOWS = [1, 5, 10, 30, 60]
GRAPH_HISTORY_MINUTES = 60

# Keep up to 3 days of data in memory (4320 minutes = 259200 seconds)
MAX_HISTORY_SECONDS = 259200

# Global data storage
log_entries = deque(maxlen=MAX_HISTORY_SECONDS)  # Each entry is a dict with time and wind speeds
current_data = {f"{w}s": 0.0 for w in TIME_WINDOWS}
current_data["last_updated"] = ""

def read_csv_file():
    """Read the CSV file and return new entries since last read"""
    try:
        if not os.path.exists(LOG_FILE):
            return []
        
        new_entries = []
        last_known_time = log_entries[-1]['time'] if log_entries else ""
        
        with open(LOG_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only add if we haven't seen this timestamp before
                if row['time'] > last_known_time:
                    # Convert wind speeds to float, handling empty values
                    entry = {'time': row['time']}
                    for window in TIME_WINDOWS:
                        try:
                            entry[f"{window}s"] = float(row[str(window)]) if row[str(window)] else None
                        except (ValueError, KeyError):
                            entry[f"{window}s"] = None
                    new_entries.append(entry)
        
        return new_entries
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []

def update_data_from_csv():
    """Continuously read CSV file and update current data"""
    last_file_size = 0
    
    while True:
        try:
            # Check if file has grown (new data available)
            if os.path.exists(LOG_FILE):
                current_size = os.path.getsize(LOG_FILE)
                if current_size != last_file_size:
                    # Read new entries
                    new_entries = read_csv_file()
                    
                    # Add new entries to our deque
                    for entry in new_entries:
                        log_entries.append(entry)
                    
                    # Update current data with most recent valid values
                    if log_entries:
                        latest_entry = log_entries[-1]
                        for window in TIME_WINDOWS:
                            window_key = f"{window}s"
                            if latest_entry[window_key] is not None:
                                current_data[window_key] = latest_entry[window_key]
                        
                        current_data["last_updated"] = latest_entry['time']
                    
                    last_file_size = current_size
            
        except Exception as e:
            print(f"Error updating data from CSV: {e}")
        
        time.sleep(1)  # Check for updates every second

def get_history_data_for_minutes(minutes):
    """Get history data for the specified number of minutes"""
    if not log_entries:
        return {f"{w}s": [] for w in TIME_WINDOWS}
    
    # Calculate cutoff time
    try:
        latest_time = datetime.datetime.strptime(log_entries[-1]['time'], "%Y-%m-%d %H:%M:%S")
        cutoff_time = latest_time - datetime.timedelta(minutes=minutes)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        # Fallback: just use the last N entries
        max_entries = minutes * 60
        relevant_entries = list(log_entries)[-max_entries:] if len(log_entries) > max_entries else list(log_entries)
        cutoff_str = relevant_entries[0]['time'] if relevant_entries else ""
    
    # Filter entries
    filtered_entries = [entry for entry in log_entries if entry['time'] >= cutoff_str]
    
    # Organize by time window
    history_data = {}
    for window in TIME_WINDOWS:
        window_key = f"{window}s"
        window_history = []
        
        for entry in filtered_entries:
            if entry[window_key] is not None:
                # Extract just the time part for display
                time_part = entry['time'].split()[1] if ' ' in entry['time'] else entry['time']
                window_history.append({
                    "time": entry['time'],
                    "time_str": time_part,
                    "mph": entry[window_key]
                })
        
        # Thin out data if too many points (for performance)
        if len(window_history) > 500:
            step = len(window_history) // 500
            window_history = window_history[::step]
        
        history_data[window_key] = window_history
    
    return history_data

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
                <thead><tr><th>Time Window</th><th>mph</th></tr></thead>
                <tbody id="readings-table"><tr><td>Loading...</td><td></td></tr></tbody>
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
        let graphHistoryMinutes = {{ graph_history_minutes }};
        
        const colors = ['#2980b9', '#27ae60', '#f39c12', '#8e44ad', '#e74c3c'];
        
        function updateCurrentData() {
            fetch('/api/current')
                .then(r => r.json())
                .then(data => {
                    // Use 10 second window for main display, fallback to any available
                    const mainSpeed = data['10s'] || data['5s'] || data['1s'] || 0;
                    document.getElementById('current-wind').textContent = mainSpeed.toFixed(2);
                    
                    document.getElementById('last-updated').textContent = data.last_updated || 'Never';
                    
                    // Update readings table
                    const windows = ['1s', '5s', '10s', '30s', '60s'];
                    const tableHtml = windows.map(w => 
                        `<tr><td>${w}</td><td>${(data[w] || 0).toFixed(2)}</td></tr>`
                    ).join('');
                    document.getElementById('readings-table').innerHTML = tableHtml;
                })
                .catch(console.error);
        }
        
        function updateHistoryChart() {
            fetch(`/api/history?minutes=${graphHistoryMinutes}`)
                .then(r => r.json())
                .then(data => {
                    const windowsToPlot = ['1s', '10s', '30s'];
                    
                    const datasets = windowsToPlot.map((windowKey, i) => {
                        const windowData = data[windowKey] || [];
                        
                        return {
                            label: `${windowKey.replace('s', ' second')} average`,
                            data: windowData.map(item => ({ 
                                x: item.time_str,
                                y: item.mph 
                            })),
                            borderColor: colors[i],
                            backgroundColor: `${colors[i]}33`,
                            tension: 0.1,
                            fill: false,
                            pointRadius: windowData.length > 100 ? 0 : 2
                        };
                    }).filter(d => d.data.length > 0);
                    
                    if (!datasets.length) return;
                    
                    // Get all unique time labels and sort them
                    const allLabels = new Set();
                    datasets.forEach(dataset => {
                        dataset.data.forEach(point => allLabels.add(point.x));
                    });
                    const sortedLabels = Array.from(allLabels).sort();
                    
                    if (windChart) {
                        windChart.data.labels = sortedLabels;
                        windChart.data.datasets = datasets;
                        windChart.update('none');
                    } else {
                        const ctx = document.getElementById('windChart').getContext('2d');
                        windChart = new Chart(ctx, {
                            type: 'line',
                            data: { 
                                labels: sortedLabels,
                                datasets: datasets 
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                interaction: { mode: 'index', intersect: false },
                                scales: {
                                    y: { 
                                        beginAtZero: true, 
                                        title: { display: true, text: 'Wind Speed (mph)' }
                                    },
                                    x: { 
                                        title: { display: true, text: 'Time' },
                                        ticks: {
                                            maxTicksLimit: 10,
                                            callback: function(value, index) {
                                                const step = Math.ceil(sortedLabels.length / 8);
                                                return index % step === 0 ? sortedLabels[index] : '';
                                            }
                                        }
                                    }
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
        setInterval(updateHistoryChart, 10000);
    </script>
</body>
</html>'''

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'wind_favicon-32x32_V2.png', mimetype='image/png')

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                graph_history_minutes=GRAPH_HISTORY_MINUTES)

@app.route('/api/current')
def get_current_data():
    return jsonify(current_data)

@app.route('/api/history')
def get_history_data():
    minutes = int(request.args.get('minutes', GRAPH_HISTORY_MINUTES))
    history_data = get_history_data_for_minutes(minutes)
    return jsonify(history_data)

def main():
    try:
        # Start background CSV reading thread
        csv_thread = threading.Thread(target=update_data_from_csv, daemon=True)
        csv_thread.start()
        
        # Check favicon file
        favicon_path = os.path.join(app.static_folder, 'wind_favicon-32x32_V2.png')
        print(f"Favicon: {'✓ Found' if os.path.exists(favicon_path) else '✗ Missing'} - {favicon_path}")
        
        # Check log file
        print(f"CSV file: {'✓ Found' if os.path.exists(LOG_FILE) else '✗ Missing'} - {LOG_FILE}")
        
        print("Starting Flask server on port 5001...")
        app.run(host='0.0.0.0', port=5001, debug=False)
        
    except KeyboardInterrupt:
        print("Stopped by user.")

if __name__ == "__main__":
    main()
