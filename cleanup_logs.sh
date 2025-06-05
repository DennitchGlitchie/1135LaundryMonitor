#!/bin/bash

# Script to clean up CSV log file by keeping the header and second half of data
# Intended to run at midnight on Wednesdays

LOG_DIR="/home/garges/WindMonitor"
TEMP_DIR="/tmp"
CSV_LOG="$LOG_DIR/wind_log.csv"

# Function to clean up CSV file
cleanup_csv_log() {
    local logfile="$1"

    if [ -f "$logfile" ]; then
        echo "Processing $logfile..."

        total_lines=$(wc -l < "$logfile")
        data_lines=$((total_lines - 1))  # Exclude header
        lines_to_keep=$((data_lines / 2))

        # Create temp file with header
        head -n 1 "$logfile" > "$TEMP_DIR/temp_csv_log_$$"

        # Append second half of data rows
        tail -n "$lines_to_keep" "$logfile" >> "$TEMP_DIR/temp_csv_log_$$"

        # Replace original file with trimmed version
        mv "$TEMP_DIR/temp_csv_log_$$" "$logfile"

        echo "Trimmed $logfile: kept header + $lines_to_keep of $data_lines data rows"
    else
        echo "CSV log file $logfile not found"
    fi
}

# Run CSV cleanup
cleanup_csv_log "$CSV_LOG"

echo "CSV log cleanup completed at $(date)"
