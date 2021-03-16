# Description

Scrips for connection test result logging to **influxDB for **Grafana** (visualization).

# Usage

* ### ping  

	python3 ping_log.py (destination\_ip) (tos)
	
	example:

	```
	$ python3 ping_log.py 8.8.8.8 4
	```
	
* ### iperf  
	python3 iperf3_log.py (destination\_ip) (destination\_port) (tos) (bitrate(M)) (reverse)
	
	example:

	```
	$ python3 iperf3_log.py 127.0.0.1 5201 44 20 0
	```
