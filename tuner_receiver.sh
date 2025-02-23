#!/bin/bash

# Activate the virtual environment
source /home/garges/nrf/bin/activate

# Loop through channels from 90 to 125
for CHANNEL in {110..125}; do
    # Run the simple-receiver_args.py script for each channel in the background using timeout
    echo "Running for Channel $CHANNEL"
    timeout 90s python3 /home/garges/simple-receiver_args.py --channel $CHANNEL --power HIGH
done
