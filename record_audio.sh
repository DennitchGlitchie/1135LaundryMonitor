#!/bin/bash

GAIN_PERCENT="${1}"
RECORD_LENGTH="${2}"
OUTPUT_FILE="${3}"
SCRIPT_DIR="$(dirname "$0")"

if [ $# -ne 3 ]; then
    echo "Usage: $0 <gain_percent> <record_length seconds> <output dir>"
    exit 1
fi

if ! command -v arecord &> /dev/null; then
    echo "Error: arecord is not installed. Please install ALSA utils package."
    exit 1
fi

if ! arecord -l | grep -q "USB Audio Device"; then
    echo "Error: USB Audio Device not found!"
    exit 1
fi

echo "Setting Mic gain to ${GAIN_PERCENT}%, turning on Auto Gain Control"
amixer sset Mic "${GAIN_PERCENT}%" > /dev/null 2>&1
amixer sset 'Auto Gain Control' on > /dev/null 2>&1

echo "Starting recording at $(date '+%Y%m%d_%H%M%S') to: ${OUTPUT_FILE} ; Recording will last for ${RECORD_LENGTH} seconds..."
echo "Press Ctrl+C to stop recording"
arecord -D hw:0,0 \
        -f cd \
        -r 44100 \
        -c 1 \
        -d "$RECORD_LENGTH" \
        -t wav \
        "$OUTPUT_FILE"

if [ $? -ne 0 ]; then
    echo "Recording failed! Check if microphone is properly connected."
    exit 1
fi

echo "Recording completed, saved to $OUTPUT_FILE updated at $(date '+%Y%m%d_%H%M%S')"
