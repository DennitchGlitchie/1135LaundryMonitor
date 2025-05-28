#!/bin/bash

# Script to remove the first half of log files
# Run this at midnight on Wednesdays

LOG_DIR="/home/garges/WindMonitor"
TEMP_DIR="/tmp"

# Function to process a log file
cleanup_log() {
    local logfile="$1"
    
    if [ -f "$logfile" ]; then
        echo "Processing $logfile..."
        
        # Count total lines
        total_lines=$(wc -l < "$logfile")
        
        # Calculate lines to keep (second half)
        lines_to_keep=$((total_lines / 2))
        
        # Create temporary file with second half
        tail -n "$lines_to_keep" "$logfile" > "$TEMP_DIR/temp_log_$$"
        
        # Replace original file with second half
        mv "$TEMP_DIR/temp_log_$$" "$logfile"
        
        echo "Reduced $logfile from $total_lines to $lines_to_keep lines"
    else
        echo "Log file $logfile not found"
    fi
}

# Process the wind log file
cleanup_log "$LOG_DIR/wind_log.jsonl"

echo "Log cleanup completed at $(date)"
