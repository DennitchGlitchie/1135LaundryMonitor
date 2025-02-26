from flask import Flask, render_template_string, jsonify
import os
import time
import re
from collections import deque
from datetime import datetime, timedelta

# Configurable threshold for determining if the machine is in use
ENERGY_THRESHOLD = 15.2

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Laundry Monitor Log</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script>
    <script>
        let chart;
        
        function updateLog() {
            fetch('/get_log')
                .then(response => response.json())
                .then(data => {
                    // Get the most recent energy value
                    const latestEnergy = data.energy_values[data.energy_values.length - 1];
                    
                    // Update status banner based on logging status and energy level
                    let statusText, statusClass;
                    if (data.is_stale) {
                        statusText = 'NOT LOGGING';
                        statusClass = 'status-not-logging';
                    } else {
                        // Compare the latest energy value with threshold
                        statusText = (latestEnergy > data.threshold) ? 'IN USE' : 'NOT IN USE';
                        statusClass = (latestEnergy > data.threshold) ? 'status-in-use' : 'status-not-in-use';
                    }
                    document.getElementById('status-banner').textContent = statusText;
                    document.getElementById('status-banner').className = statusClass;
                    
                    // Update timestamp
                    document.getElementById('last-updated').textContent = `as of ${data.latest_timestamp}`;
                    
                    // Update log content
                    document.getElementById('log-content').innerHTML = data.log_text;
                    
                    // Update chart
                    if (!chart) {
                        const ctx = document.getElementById('energyChart').getContext('2d');
                        chart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: data.timestamps,
                                datasets: [{
                                    label: 'Energy at 60Hz',
                                    data: data.energy_values,
                                    borderColor: 'rgb(75, 192, 192)',
                                    tension: 0.1
                                },
                                {
                                    label: 'Threshold',
                                    data: Array(data.timestamps.length).fill(data.threshold),
                                    borderColor: 'rgba(255, 0, 0, 0.5)',
                                    borderDash: [5, 5],
                                    pointRadius: 0,
                                    fill: false
                                }]
                            },
                            options: {
                                responsive: true,
                                scales: {
                                    y: {
                                        min: 15,
                                        max: 17.5
                                    }
                                }
                            }
                        });
                    } else {
                        chart.data.labels = data.timestamps;
                        chart.data.datasets[0].data = data.energy_values;
                        chart.data.datasets[1].data = Array(data.timestamps.length).fill(data.threshold);
                        chart.update();
                    }
                });
        }
        
        // Update every 5 seconds
        setInterval(updateLog, 5000);
        
        // Initial load
        window.onload = updateLog;
    </script>
    <style>
        body {
            font-family: monospace;
            margin: 20px;
            background-color: #f0f0f0;
        }
        .title {
            font-size: 48px;
            text-align: center;
            margin-bottom: 10px;
        }
        #status-banner {
            font-size: 48px;
            text-align: center;
            padding: 20px;
            margin-bottom: 5px;
            border-radius: 10px;
            font-weight: bold;
        }
        .description {
            text-align: center;
            font-size: 16px;
            margin: 10px 0 20px 0;
            padding: 0 20px;
            line-height: 1.4;
        }
        .status-in-use {
            background-color: #FFB6C1;
            color: #8B0000;
        }
        .status-not-in-use {
            background-color: #90EE90;
            color: #006400;
        }
        .status-not-logging {
            background-color: #FFD700;
            color: #8B4513;
        }
        #last-updated {
            text-align: center;
            font-size: 14px;
            margin-bottom: 20px;
            color: #666;
        }
        #log-content {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            white-space: pre-wrap;
            margin-bottom: 20px;
        }
        .chart-container {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .footer {
            text-align: center;
            font-size: 14px;
            margin-top: 20px;
            margin-bottom: 20px;
            color: #444;
        }
        .footer a {
            color: #0066cc;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="title">The Laundry Machine at 1135 Masonic is:</div>
    <div id="status-banner">Loading...</div>
    <div id="last-updated"></div>
    <div class="description">
        This Laundry Monitor monitors the amount of power going into the washing machine. It will only indicate IN USE when the machine is running. It will not tell you if there are clothes in the machine.
        <br>
        Feel free to buy me a coffee <a href="https://buymeacoffee.com/davidgarges" target="_blank">https://buymeacoffee.com/davidgarges</a>
        <br>
        -David Garges Apt #5
    </div>
    <div class="chart-container">
        <canvas id="energyChart"></canvas>
    </div>
    <div id="log-content"></div>
</body>
</html>
"""

LOG_FILE = '/home/garges/LaundryMonitor/history.log'

# Keep track of last 400 energy readings
energy_history = deque(maxlen=400)
timestamp_history = deque(maxlen=400)

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_log')
def get_log():
    try:
        # Read the last 100 lines of the log file
        with open(LOG_FILE, 'r') as f:
            content = f.read()
            
        # Split into paragraphs
        paragraphs = content.strip().split('\n\n')
        # Take last 400 paragraphs
        recent_paragraphs = paragraphs[-400:]
        
        # Get the timestamp from the last paragraph
        latest_timestamp = ''
        is_stale = False
        
        if recent_paragraphs:
            # Get timestamp from the first line of the last paragraph
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', recent_paragraphs[-1])
            if timestamp_match:
                latest_timestamp = timestamp_match.group(1)
                # Check if log is stale (more than 2 minutes old)
                last_time = datetime.strptime(latest_timestamp, '%Y-%m-%d %H:%M:%S')
                is_stale = (datetime.now() - last_time) > timedelta(minutes=2)
        
        # Update energy history
        energy_history.clear()
        timestamp_history.clear()
        
        for paragraph in recent_paragraphs:
            energy_match = re.search(r'energy at 60Hz: (\d+\.\d+)', paragraph)
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', paragraph)
            
            if energy_match and timestamp_match:
                energy_value = float(energy_match.group(1))
                # Only add to history if energy is between 15 and 17.5
                if 15 <= energy_value <= 17.5:
                    energy_history.append(energy_value)
                    timestamp_history.append(timestamp_match.group(1))
        
        return jsonify({
            'log_text': '\n\n'.join(recent_paragraphs),
            'latest_timestamp': latest_timestamp,
            'is_stale': is_stale,
            'energy_values': list(energy_history),
            'timestamps': list(timestamp_history),
            'threshold': ENERGY_THRESHOLD  # Use the configurable threshold
        })
    except Exception as e:
        return jsonify({
            'log_text': f"Error reading log file: {str(e)}",
            'latest_timestamp': '',
            'is_stale': True,
            'energy_values': [],
            'timestamps': [],
            'threshold': ENERGY_THRESHOLD  # Use the configurable threshold
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
