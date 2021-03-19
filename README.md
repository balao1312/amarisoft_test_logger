## Description

Scrips for connection test result logging to **influxDB** for **Grafana** (visualization).  
Use **Python** to get real-time output from Linux shell command with buffer design.  
Result will be log to plain text file and send to database periodically.

## Requirements

Linux based environment or Macintosh with tool **iperf3** installed.  

## Usage

* ### ping
	Test connection latency.  
	Syntax : `python3 ping_log.py (destination\_ip) (tos)`  
	Example:
	
	```
	$ python3 ping_log.py 8.8.8.8 4
	```
	
* ### iperf  
	Test connection thoughtput.  
	Syntax : `python3 iperf3_log.py (destination\_ip) (destination\_port) (tos) (bitrate(M)) (reverse)`  
	example:

	```
	$ python3 iperf3_log.py 127.0.0.1 5201 44 20 0
	```
* ### resources
	Log resources usage of base station computer. (usually placed in linux crontab)    
	Syntax : `python3 resources_log.py`  
	example:  
	
	```
	$ python3 resources_log.py
	```
	
## Screenshot
![alt text](https://github.com/balao1312/amarisoft_test_logger/blob/master/alogger.png?raw=true)