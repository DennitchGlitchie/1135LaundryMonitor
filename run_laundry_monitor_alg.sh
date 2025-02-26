#!/bin/bash
NOW_LOG="now.log"
DEBUG_LOG="debug.log"
HISTORY_LOG="history.log"
ADDRESS="1SNSR"
CHANNEL=96
POWER="HIGH" 
NRF_ENV="/home/garges/nrf/bin/activate"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
AUDIO_RECEIVE_SCRIPT="${SCRIPT_DIR}/receive_audio_analysis.py"
AMPLITUDE_ALGORITHM_THRESHOLD=15.2

##############################################################
##############################################################

cleanup() {
    echo "Stopping ${AUDIO_RECEIVE_SCRIPT}..."
    kill "$AUDIO_RECEIVE_PID" 2>/dev/null
}

log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${DEBUG_LOG}"
}

get_energy_value() {
    local freq="$1"
    local value=$(grep "energy at ${freq}Hz:" "${NOW_LOG}" 2>/dev/null | awk '{print $4}')
    
    # Return N/A if frequency not found
    if [ -z "$value" ]; then
        echo "N/A"
    else
        echo "$value"
    fi
}

evaluate_amplitude_algorithm() {
    local energy_60Hz=$(get_energy_value 60)
    
    if [ "$energy_60Hz" = "N/A" ]; then
        echo "AMPLITUDE_ALGORITHM=NULL (60Hz energy not available)"
    else
        if (( $(echo "$energy_60Hz > ${AMPLITUDE_ALGORITHM_THRESHOLD}" | bc -l) )); then
            echo "AMPLITUDE_ALGORITHM=ON (60Hz energy: $energy_60Hz > ${AMPLITUDE_ALGORITHM_THRESHOLD})"
        else
            echo "AMPLITUDE_ALGORITHM=OFF (60Hz energy: $energy_60Hz <= ${AMPLITUDE_ALGORITHM_THRESHOLD})"
        fi
    fi
}

evaluate_ratio_algorithm() {
    local energy_60Hz=$(get_energy_value 60)
    local energy_180Hz=$(get_energy_value 180)
    
    if [ "$energy_60Hz" = "N/A" ] || [ "$energy_180Hz" = "N/A" ]; then
        echo "RATIO_ALGORITHM=NULL (Required energies not available)"
    else
        local ratio=$(echo "$energy_180Hz / $energy_60Hz" | bc -l)
        if (( $(echo "$ratio > 0.20" | bc -l) )); then
            echo "RATIO_ALGORITHM=ON (180Hz/60Hz ratio: $ratio > 0.20)"
        else
            echo "RATIO_ALGORITHM=OFF (180Hz/60Hz ratio: $ratio <= 0.20)"
        fi
    fi
}

##############################################################
##############################################################

source "${NRF_ENV}"
trap cleanup EXIT

log_with_timestamp "Starting ${AUDIO_RECEIVE_SCRIPT} in the background with channel ${CHANNEL} and power ${POWER}..."
python3 "${AUDIO_RECEIVE_SCRIPT}" --channel "${CHANNEL}" --power "${POWER}" --logfile "${NOW_LOG}" >> "${DEBUG_LOG}" 2>&1 &
AUDIO_RECEIVE_PID=$!

LAST_MODIFIED=$(stat -c %Y "${NOW_LOG}" 2>/dev/null || echo 0)

while true; do
    log_with_timestamp "==============================" 
    log_with_timestamp "Starting the loop..."
    CURRENT_MODIFIED=$(stat -c %Y "${NOW_LOG}" 2>/dev/null || echo 0)
    if [ "$CURRENT_MODIFIED" -gt "$LAST_MODIFIED" ]; then

        log_with_timestamp "${NOW_LOG} has been updated. Recording to ${HISTORY_LOG}"
        echo "$(date '+%Y-%m-%d %H:%M:%S')" >> "$HISTORY_LOG"
        echo "FREQUENCY VALUES:" >> "${HISTORY_LOG}"
        cat "${NOW_LOG}" >> "${HISTORY_LOG}"

        echo "ALGORITHM EVALUATIONS:" >> "${HISTORY_LOG}"
        evaluate_amplitude_algorithm >> "${HISTORY_LOG}"
        evaluate_ratio_algorithm >> "${HISTORY_LOG}"
        echo "" >> "${HISTORY_LOG}"
        
        LAST_MODIFIED=$CURRENT_MODIFIED
    else
        log_with_timestamp "No updates to ${NOW_LOG} detected"
    fi
    
    sleep 5
done
