The purpose of this project is to monitor the single laundry machine (shared by 12 apartment units) to be able to identify if it is "in use" or "not in use. I used a raspberry pi to monitor a current clamp around the power cable of the laundry machine. Since there is no internet downstairs, I used a secondary raspberry pi and NRF24 transcievers to transmit information. The secondary raspberry pi hosts a webserver with the laundry monitor information.

BOM:
- Raspberry Pi 4 Model B Running DietPi OS
- [NRF24 Transcievers](https://buymeacoffee.com/davidgarges](https://www.amazon.com/dp/B00WG9HO6Q?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1))
- [USB Sound Card Adapter](https://www.amazon.com/dp/B0BQBT2LCV?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_3)
- [1ft Extension Cable](https://www.amazon.com/your-orders/orders?_encoding=UTF8&startIndex=20&ref_=ppx_yo2ov_dt_b_pagination_2_3)
- [Mounting Box](https://www.amazon.com/dp/B0D5GPMPT1?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1&th=1)
- [USB Extension Cable](https://www.amazon.com/dp/B0793P8XJK?ref=ppx_yo2ov_dt_b_fed_asin_title)
- Raspberry Pi 4 Model B Running Raspberry Pi OS

This project uses a cloud-based Virtual Machine (VM) as the central access point for all my Raspberry Pi devices. Each Raspberry Pi establishes a reverse SSH connection to the cloud VM, which facilitates secure remote access and port forwarding for both SSH and web services. In particular, port 6083 is used to forward HTTP traffic from the cloud VM to the Raspberry Pi's local web server, enabling secure access to web services hosted on the Pi.

The cloud VM is at 34.19.58.168 hosted by Google Cloud Console
|                                                           | Rasberry Pi User | Cloud VM User | User that Sets up the Tunnel | Cloud VM Command             | Reverse Tunnel Command                                                                         |
|-----------------------------------------------------------|------------------|---------------|------------------------------|------------------------------|------------------------------------------------------------------------------------------------|
| Laundry Monitor (DietPi) <- Cloud Virtual Machine         | root             | david_garges  | laundry_monitor              | ssh -p 6002 root@localhost   | ssh -N -R 0.0.0.0:6002:localhost:22 -i /root/.ssh/cloud_vm2 laundry_monitor@34.19.58.168       |
| Home Assistant (Raspberry Pi OS) <- Cloud Virtual Machine | garges           | david_garges  | home_assistant               | ssh -p 6003 garges@localhost | ssh -N -R 0.0.0.0:6003:localhost:22 -i /home/garges/.ssh/cloud_vm2 home_assistant@34.19.58.168 |

Setting up the NRF24 Modules:
- The Wiring of the NR24 to the Raspbery Pis are as follows:

| NRF Pin | Raspberry Pi Pin | Raspberry Pi Function |
|---------|------------------|-----------------------|
| VCC     | 1                | 3.3V DC Power         |
| GND     | 6                | GND                   |
| CE      | 11               | GPIO17 (GPIO_GEN0)    |
| MOSI    | 19               | GPIO10 (SPI_MOSI)     |
| MISO    | 21               | GPIO09 (SPI_MISO)     |
| SCK     | 23               | GPIO11 (SPI_CLK)      |
| CSN     | 24               | GPIO08 (SPI_CE0_N)    |
| IRQ     | 18               | GPIO24                |

- I struggled with successful transmission FOREVER. Solution: 100 pF from VCC to GND at the NRF24 module
- Had to use a virtual python environment to install https://pypi.org/project/nrf24/
- NOTE: this python package uses pigpiod which has a hard time restarting over and over again. The software design had to adapt to this
- Once installed, I used tuner_receiver.sh and tuner_transmitter.sh to tune the channel. I ended up choosing channel 96 with power level HIGH
- Used simple_transmitter.py and simple_receiver.py as a test and guide from https://github.com/bjarne-hansen/py-nrf24

On the Transmit Side:
- autossh.service: set up a reverse tunne to the cloud VM (there is no internet normally on the transmit side)
- laundry-trasnmitter.service: start record_process_send.sh at boot
- record_process_send.sh: Main process, starts send_audio_analysis.py, loops through record_audio.sh and process_audio.py and generating now.log (with a now_buffer.log)
- record_audio.sh: Records 1 second of audio and saves it to now.wav
- process_audio.py: Processes now.wav to generate FFT values. Finds the energy at 60Hz (and other frequencies) as the squared magnitude of the FFT. Is then normalized using a logarithmic scale.
- send_audio_analysis.py: Runs in parrallel, monitor now.log, sends the energy values over the channel
- now.log and now_buffer.log: Updated version of the audio analysis, with buffer since now.log is monitored for changes
- debug.log: debug output

On the Receiver Side:
- autossh.service: set up a reverse tunne to the cloud VM
- run_laundry_monitor_alg.sh: Main process, starts receive_audio_analysis.py, provides algorithm evaluations
- receive_audio_analysis.py: Runs in parrallel, generates now.log with data from transmitter
- now.log: Regenerated audio analysis on the reciever side
- debug.log: debug output
- history.log: History of now.log
- laundry_webserver.py: Creates the Flask Webserver

Detailed Description of Receiver Software Design
run_laundry_monitor_alg.sh is the main process. It send_audio_analysis.py because the pigpiod service can't be started and stopped. A loop is started (currently 10 second delay) where record_audio.sh is ran to generate now.wav. The python file process_audio.py which has a dictionary to select frequencies for analysis. Any combination of frequencies can be selected and additional can be added. Currently the algorithm is only focussing on 60Hz and the rest are useless.

frequencies = {
    'Energy60Hz': 60,
    'Energy180Hz': 180,
#    'Energy300Hz': 300,
#    'Energy430Hz': 430,
#    'Energy540Hz': 540
} 

process_audio will generate a now_buffer.log text file which will be transferred to now.log by record_process_send.sh. It will look something like this.

energy at 60Hz: 15.0389
energy at 180Hz: 13.6403

send_audio_analysis.py will check now.log every 5 seconds for and update. If it sees an update, it will scrape this file and packetize the data. It uses a dynamic payload. For each frequency pair, it packs:
- A count of the frequency pairs
- The frequency number as a 2-byte unsigned integer (uint16)
- The frequency value as a 4-byte float (float32)

[count][freq1_num][freq1_value][freq2_num][freq2_value]...
  1B      2B         4B          2B         4B

The maximumpayload size is 32, which means 
- Available space for frequency pairs = 32 bytes - 1 byte (for count) = 31 bytes
- Number of pairs = 31 bytes ÷ 6 bytes per pair = 5.16 pairs or effectively 5 pairs.





Webserver:
- laundry_webserver.py is AI generated so I designed it's overall function. My goal was to have a status icon at the top "IN USE", "NOT IN USE", "NOT LOGGING". Also a graph of all the recent past readings. Also an output of the history.log file for debugging purposes.
- Since I own davidgarges.com, I created a custom record for 1135laundrymonitor to be routed to 34.19.58.168. Since I have other web services running on the pi, I used nginx to route based on the DNS(?) lookup. I also used nginx to provide SSL such that I can use https.
- /etc/nginx/sites-available/1135laundrymonitor
- sudo ln -s /etc/nginx/sites-available/1135laundrymonitor /etc/nginx/sites-enabled/
- port translation 6083 to 80

Vulnerabilities:
- I am constantly logging on both pis, and i am concerned we will fill up on the disk space eventually.
- SSL expiration, I haven't done this before so I may have to keep renewing it
- I got my previous cloud VM hacked or somehting and I may have to completely recreate the cloud VM setup like I did over the last 8 months. 

