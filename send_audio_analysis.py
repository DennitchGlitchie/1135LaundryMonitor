import argparse
import struct
import sys
import time
import traceback
import os
import pigpio
from nrf24 import *

def print_with_header(message):
    header = f"[AUDIO_SEND_SCRIPT at {time.strftime('%Y-%m-%d %H:%M:%S')}]"
    print(f"{header}: {message}", flush=True)

def read_frequencies_from_log(log_file):
    try:
        frequencies = {}
        with open(log_file, "r") as file:
            for line in file:
                if line.startswith("energy at ") and "Hz:" in line:
                    parts = line.strip().split("Hz: ")
                    freq_value = float(parts[1])
                    freq_num = int(parts[0].replace("energy at ", ""))
                    frequencies[freq_num] = freq_value
        return frequencies
    except Exception as e:
        print_with_header(f"Error reading frequencies from {log_file}: {str(e)}")
        return None

def monitor_log_file(log_file):
    last_modified_time = os.path.getmtime(log_file)
    while True:
        current_modified_time = os.path.getmtime(log_file)
        if current_modified_time != last_modified_time:
            last_modified_time = current_modified_time
            yield True
        time.sleep(1)

def packetize_data(frequencies):
    """
    Packetize frequency data into a single packet with size limit checking
    """
    # Start with one byte for the count
    packet_size = 1
    payload = bytearray()
    
    # Sort frequencies for consistent ordering
    sorted_frequencies = sorted(frequencies.items())
    
    # Reserve the first byte for count, will fill it in at the end
    payload.append(0)  # Placeholder for count
    
    # Track which frequencies were successfully packed
    packed_items = []
    
    for freq_num, freq_value in sorted_frequencies:
        # Each frequency pair needs 6 bytes: 2 for freq_num (uint16) and 4 for freq_value (float32)
        item_size = 6
        
        # Check if adding this item would exceed the 32 byte limit
        if packet_size + item_size > 32:
            print_with_header(f"WARNING: Cannot fit freq {freq_num}={freq_value} in packet - would exceed 32 byte limit")
            continue
        
        # Pack this frequency pair
        freq_bytes = struct.pack("<Hf", freq_num, freq_value)
        payload.extend(freq_bytes)
        packet_size += item_size
        packed_items.append((freq_num, freq_value))
        
        print_with_header(f"Packed: freq={freq_num}, value={freq_value}, running size={packet_size} bytes")
    
    # Update the count at the beginning of the payload
    count = len(packed_items)
    payload[0] = count
    
    print_with_header(f"Final packet: {count} items, {packet_size} bytes total")
    print_with_header(f"Items packed: {packed_items}")
    
    return payload

def send_data(nrf, log_file):
    frequencies = read_frequencies_from_log(log_file)
    
    if not frequencies:
        print_with_header("Error: Could not read frequencies, skipping.")
        return False

    print_with_header(f"Read frequencies from log: {frequencies}")
    
    payload = packetize_data(frequencies)
    
    print_with_header(f"Payload length: {len(payload)} bytes")
    print_with_header(f"Payload (hex): {' '.join(f'{x:02x}' for x in payload)}")
    
    nrf.reset_packages_lost()
    nrf.send(payload)
    
    try:
        nrf.wait_until_sent()
    except TimeoutError:
        print_with_header('Timeout waiting for transmission to complete.')
        time.sleep(10)
        return False
    
    if nrf.get_packages_lost() == 0:
        print_with_header(f"Success: lost={nrf.get_packages_lost()}, retries={nrf.get_retries()}")
        return True
    else:
        print_with_header(f"Error: lost={nrf.get_packages_lost()}, retries={nrf.get_retries()}")
        return False

if __name__ == "__main__":    
    print_with_header("Python NRF24 Simple Sender Example.")
    
    parser = argparse.ArgumentParser(prog="send_audio.py", description="Send Audio Data over NRF24.")
    parser.add_argument('--channel', type=int, default=90, help="Channel to use (default: 90).")
    parser.add_argument('--power', type=str, choices=['LOW', 'MEDIUM', 'HIGH'], default='LOW', help="Power level (default: LOW).")
    parser.add_argument('--logfile', type=str, default='now.log')
    
    args = parser.parse_args()
    channel = args.channel
    power_level = args.power
    log_file = args.logfile
    address = "1SNSR"

    if power_level == 'LOW':
        power = RF24_PA.LOW
    elif power_level == 'MEDIUM':
        power = RF24_PA.MEDIUM
    elif power_level == 'HIGH':
        power = RF24_PA.HIGH

    print_with_header(f"Using address {address}, channel {channel}, and power {power_level}")
    
    pi = pigpio.pi("localhost", 8888)
    if not pi.connected:
        print_with_header("Not connected to Raspberry Pi ... goodbye.")
        sys.exit()

    nrf = NRF24(pi, ce=25, payload_size=RF24_PAYLOAD.DYNAMIC, channel=channel, 
                data_rate=RF24_DATA_RATE.RATE_250KBPS, pa_level=power)
    nrf.set_address_bytes(len(address))
    nrf.open_writing_pipe(address)
    nrf.show_registers()

    try:
        print_with_header(f'Send to {address} using channel {channel} and power {power_level}')
        
        log_monitor = monitor_log_file(log_file)
        for _ in log_monitor:
            print_with_header(f"detected change of {log_file}")
            send_data(nrf, log_file)
            time.sleep(5)

    except:
        traceback.print_exc()
        nrf.power_down()
        pi.stop()
