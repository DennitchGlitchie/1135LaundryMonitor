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
- using virtual python environment
- soldering capacitors
- pigpio and it's inability to start/restart and how it defines the algorithm
- Tuning both sides of the tunnel
- tuner_receiver.sh and tuner_transmitter.sh

On the Transmit Side:
- record_process_send.sh
- record_audio.sh
- process_audio.py
- send_audio_analysis.py
- now.log and now_buffer.log
- debug.log

On the Receiver Side:
- run_laundry_monitor_alg.sh
- receive_audio_analysis.py
- now.log
- debug.log
- history.log

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

