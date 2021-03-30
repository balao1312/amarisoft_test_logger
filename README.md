## Description

Scrips for connection test result logging to **influxDB** for **Grafana** (visualization).  
Use **Python** to get real-time output from Linux shell command with buffer design.  
Result will be log to plain text file and send to database periodically.

## Requirements

- Linux based environment or Macintosh with tool **iperf3** installed  
- Running influxdb server  
- Grafana service to visualize data in influxdb (optional)
- Pip install -r requirements.txt

## Usage

* ### ping
	Test connection latency.  
	Syntax : `python3 ping_log.py (destination ip) (tos)`  
	Example:
	
	```
	$ python3 ping_log.py 8.8.8.8 4
	```
	
* ### iperf  
	Test connection thoughtput.  
	Syntax : `python3 iperf3_log.py (destination ip) (destination port) (tos) (bitrate(M)) (reverse)`  
	example:

	```
	$ python3 iperf3_log.py 127.0.0.1 5201 44 20 0
	```
* ### resources
	Log resources usage of base station computer. (usually put in linux crontab) (linux only)   
	Syntax : `python3 resources_log.py`  
	example:  
	
	```
	$ python3 resources_log.py
	```
	
* ### parse and send
	Parse those log files generated without internet connection.  
	Take file or folder path as argument  
	Syntax : `python3 parse_and_send.py (path)`  
	example:  
	
	```
	$ python3 parse_and_send.py logs
	```

* ### watch dog parsing
	Create a folder or use an existing one to wait for log file to pass in.  
	Once detected new file, this will automatic parse those files and send to db.   
	Syntax : `python3 watch_dog_parsing.py`  
	example:  
	
	```
	$ python3 watch_dog_parsing.py 
	```  

## Note

Database config defined in credential.py:
	
```
db_config = {
	'influxdb_ip': (your influxdb server ip),
	'influxdb_port': (your influxdb server port),
	'influxdb_username': (your influxdb server username),
	'influxdb_password': (your influxdb server password),
	'influxdb_dbname': (your database name),
}
```
  
## Screenshot
![alt text](https://github.com/balao1312/amarisoft_test_logger/blob/master/alogger.png?raw=true)
![alt text](https://github.com/balao1312/amarisoft_test_logger/blob/master/watchdogex.png?raw=true)