#!/usr/bin/env python3

import sys
import numpy as np
from scipy import io
from scipy.fft import fft
import argparse

frequencies = {
    'Energy60Hz': 60,
    'Energy180Hz': 180,
#    'Energy300Hz': 300,
#    'Energy430Hz': 430,
#    'Energy540Hz': 540
}  

def compute_energy(audio_file, frequencies):
    """Compute energy at specified frequencies from audio file."""
    try:
        samplerate, data = io.wavfile.read(audio_file)                                  # Read the audio file  
        if len(data.shape) > 1:                                                         # Convert stereo to mono if necessary
            data = np.mean(data, axis=1)
            
        N = len(data)                                                                   # Compute FFT
        T = 1.0 / samplerate
        yf = fft(data)
        xf = np.fft.fftfreq(N, T)[:N//2]
        
        energy = {}                                                                     # Calculate energy at specified frequencies
        for label, freq in frequencies.items():            
            index = np.argmin(np.abs(xf - freq))                                        # Find the nearest frequency index
            if index < len(yf):                                                         # Compute energy and normalize
                energy[label] = float(np.abs(yf[index]) ** 2)
                
                energy[label] = np.log10(energy[label] + 1)  # Add 1 to avoid log(0)    # Normalize to a more manageable range
            else:
                energy[label] = 0.0
        return energy, xf
    
    except Exception as e:
        print(f"Error in compute_energy: {str(e)}", file=sys.stderr)
        return None, None

def update_log_file(log_file, energy):
    """Update log file with the frequency values, in the required format."""
    try:
        with open(log_file, "w") as file:                                               # Open the log file in 'w' mode to overwrite it
            for label, energy_value in energy.items():
                frequency = label.replace('Energy', '').replace('Hz', '')
                file.write(f"energy at {frequency}Hz: {energy_value:.4f}\n")
            
        print(f"Updated {log_file} with the following frequency energies:")
        for label, energy_value in energy.items():
            frequency = label.replace('Energy', '').replace('Hz', '')
            print(f"energy at {frequency}Hz: {energy_value:.4f}")
    except Exception as e:
        print(f"Error updating log file: {str(e)}", file=sys.stderr)

def main():
    """Main function to process audio and log results."""
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Process an audio file and update the log file with energy values.")
    parser.add_argument('audio_file', type=str, help="Input WAV audio file (e.g., now.wav)")
    parser.add_argument('log_file', type=str, help="Output log file (e.g., now.log)")
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Compute energy values using the frequencies dictionary
        energy, xf = compute_energy(args.audio_file, frequencies)
        if energy is None:
            sys.exit(1)
        
        # Update log file with frequency values
        update_log_file(args.log_file, energy)
        
    except Exception as e:
        print(f"Error in main: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
