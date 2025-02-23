import argparse
import struct
import sys
import time
import traceback
import os
import pigpio
from nrf24 import *

def print_with_header(message):
    header = f"[AUDIO_RECEIVE_SCRIPT at {time.strftime('%Y-%m-%d %H:%M:%S')}]"
    print(f"{header}: {message}", flush=True)

# Function to update now.log with received frequency values
def update_log_file(log_file, frequency_data):
    try:
        # Overwrite the log file with the latest frequency data
        with open(log_file, 'w') as file:
            for freq_num, freq_value in sorted(frequency_data.items()):
                file.write(f"energy at {freq_num}Hz: {freq_value:.4f}\n")
        
        print_with_header(f"Updated {log_file} with {len(frequency_data)} frequency entries")
    except Exception as e:
        print_with_header(f"Error updating {log_file}: {e}")

def decode_payload(payload):
    """
    Decode the payload received from the sender script
    Returns a dictionary of frequency number -> energy value
    """
    if len(payload) < 1:
        print_with_header("Error: Empty payload received")
        return None
    
    # First byte is the count of frequency pairs
    count = payload[0]
    print_with_header(f"Payload contains {count} frequency pairs")
    
    # Each frequency pair is 6 bytes (2 for freq_num as uint16, 4 for freq_value as float32)
    expected_len = 1 + (count * 6)
    if len(payload) < expected_len:
        print_with_header(f"Error: Payload too short. Expected {expected_len} bytes, got {len(payload)}")
        return None
    
    # Extract frequency pairs
    frequencies = {}
    for i in range(count):
        # Calculate position in the payload
        pos = 1 + (i * 6)
        
        # Extract the frequency number and value
        try:
            freq_num = struct.unpack("<H", payload[pos:pos+2])[0]
            freq_value = struct.unpack("<f", payload[pos+2:pos+6])[0]
            frequencies[freq_num] = freq_value
            print_with_header(f"Decoded frequency pair {i+1}/{count}: {freq_num}Hz = {freq_value:.4f}")
        except struct.error as e:
            print_with_header(f"Error unpacking frequency pair at position {pos}: {e}")
            continue
    
    return frequencies

if __name__ == "__main__":
    print_with_header("Python NRF24 Simple Receiver Example.")
    
    # Parse command line argument.
    parser = argparse.ArgumentParser(prog="receive_audio.py", description="Receive Audio Data over NRF24.")
    parser.add_argument('-n', '--hostname', type=str, default='localhost', help="Hostname for the Raspberry running the pigpio daemon.")
    parser.add_argument('-p', '--port', type=int, default=8888, help="Port number of the pigpio daemon.")
    parser.add_argument('--address', type=str, default='1SNSR', help="Address to listen to (3 to 5 ASCII characters)")
    parser.add_argument('--channel', type=int, default=90, help="RF Channel (default: 90).")
    parser.add_argument('--power', type=str, choices=['LOW', 'MEDIUM', 'HIGH'], default='HIGH', help="Power level (default: HIGH).")
    parser.add_argument('--logfile', type=str, default='now.log', help="Log file to update (default: now.log).")
    
    args = parser.parse_args()
    hostname = args.hostname
    port = args.port
    address = args.address
    channel = args.channel
    power_level = args.power
    log_file = args.logfile
    
    # Verify that address is between 3 and 5 characters.
    if not (2 < len(address) < 6):
        print_with_header(f'Invalid address {address}. Addresses must be between 3 and 5 ASCII characters.')
        sys.exit(1)
    
    # Convert power level string to appropriate enum value
    if power_level == 'LOW':
        power = RF24_PA.LOW
    elif power_level == 'MEDIUM':
        power = RF24_PA.MEDIUM
    elif power_level == 'HIGH':
        power = RF24_PA.HIGH
    
    # Connect to pigpiod
    print_with_header(f'Connecting to GPIO daemon on {hostname}:{port} ...')
    pi = pigpio.pi(hostname, port)
    if not pi.connected:
        print_with_header("Not connected to Raspberry Pi ... goodbye.")
        sys.exit()
    
    # Create NRF24 object with dynamic payload size, using the passed channel and power level
    nrf = NRF24(pi, ce=25, payload_size=RF24_PAYLOAD.DYNAMIC, channel=channel, 
                data_rate=RF24_DATA_RATE.RATE_250KBPS, pa_level=power)
    nrf.set_address_bytes(len(address))
    
    # Listen on the address specified as parameter
    nrf.open_reading_pipe(RF24_RX_ADDR.P0, address)
    
    # Display the content of NRF24L01 device registers.
    nrf.show_registers()
    
    # Enter a loop receiving data on the address specified.
    try:
        print_with_header(f'Receiving from {address} on channel {channel} with power {power_level}')
        count = 0
        while True:
            # As long as data is ready for processing, process it.
            while nrf.data_ready():
                # Count message and record time of reception.            
                count += 1
                now = time.time()
                
                # Read pipe and payload for message.
                pipe = nrf.data_pipe()
                payload = nrf.get_payload()    
                
                # Debugging: Print the raw payload in hex format
                print_with_header(f"Raw payload received (hex): {' '.join(f'{x:02x}' for x in payload)}")
                
                # Show message received as hex.
                print_with_header(f"Received: pipe: {pipe}, len: {len(payload)}, bytes: {' '.join(f'{x:02x}' for x in payload)}, count: {count}")
                
                # Decode the payload
                frequency_data = decode_payload(payload)
                
                if frequency_data:
                    # Update now.log with received frequency values
                    update_log_file(log_file, frequency_data)
                else:
                    print_with_header("Failed to decode payload, skipping log update")
                
            # Sleep 100 ms.
            time.sleep(0.1)
    except:
        traceback.print_exc()
        nrf.power_down()
        pi.stop()

garges@raspberrypi:~/LaundryMonitor $ 
