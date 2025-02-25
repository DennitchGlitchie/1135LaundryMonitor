#!/bin/bash

AUDIO_FILE="now.wav"
NOW_LOG="now.log"
NOW_BUFFER_LOG="now_buffer.log"
ARCHIVE_LOG="laundry_monitor.log"
AUDIO_RECORD_SCRIPT="record_audio.sh"
AUDIO_PROCESS_SCRIPT="process_audio.py"
AUDIO_SEND_SCRIPT="send_audio_analysis.py"
ADDRESS="1SNSR"
CHANNEL=96           
POWER="HIGH"         
NRF_ENV="$HOME/nrf/bin/activate"
AUDIO_GAIN=5
RECORD_LENGTH=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

##############################################################
##############################################################

log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${ARCHIVE_LOG}"
}

cleanup() {
    log_with_timestamp "Stopping ${AUDIO_SEND_SCRIPT}..."
    kill "${AUDIO_SEND_PID}" 2>/dev/null
}

##############################################################
##############################################################

source "${NRF_ENV}"
trap cleanup EXIT

log_with_timestamp "Starting ${AUDIO_SEND_SCRIPT} in the background with channel ${CHANNEL} and power ${POWER}..."
nohup python3 "${AUDIO_SEND_SCRIPT}" --channel "${CHANNEL}" --power "${POWER}" --logfile ${NOW_LOG} >> "${ARCHIVE_LOG}" 2>&1 & 
AUDIO_SEND_PID=$!

while true; do
    log_with_timestamp "----------------------------------------------------------"
    log_with_timestamp "---------------Starting Record/Process Loop---------------"
    log_with_timestamp "----------------------------------------------------------"
    
    log_with_timestamp "Recording audio..."
    "${SCRIPT_DIR}/${AUDIO_RECORD_SCRIPT}" "${AUDIO_GAIN}" "${RECORD_LENGTH}" "${AUDIO_FILE}">> "${ARCHIVE_LOG}" 2>&1

    log_with_timestamp "Processing audio..."
    python3 "${SCRIPT_DIR}/${AUDIO_PROCESS_SCRIPT}" "${AUDIO_FILE}" "${NOW_BUFFER_LOG}" >> "${ARCHIVE_LOG}" 2>&1
    
    log_with_timestamp "Writing to from ${NOW_BUFFER_LOG} to ${NOW_LOG}"
    cat "${NOW_BUFFER_LOG}" > "${NOW_LOG}"

    sleep 10
done
