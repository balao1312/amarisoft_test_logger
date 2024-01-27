## Description
Some Python scrips for monitoring output from native network connection quality measurement tools like "ping", and "iperf3".  
These scrips will capture real-time output and log to database **influxDB**, and easy to be visualized with **Grafana**.  
Notify (through the App - Line) when connection quility is meet user customized criteria is supported.

## Requirements
- Linux based environment or Macintosh with tool iperf3(version 3.7+) installed  
- (optional) Influxdb database
- (optional) Grafana service to visualize
- (optional) App - Line notify token

## Install dependencies package
`$ Pip3 install -r requirements.txt`

## Usage

* ### ping
	Measure connection latency.  
	Syntax : `python3 ping_logger.py [options like origin iperf3 options]`  
	Example:
	
	```
	$ python3 ping_logger.py -c 8.8.8.8 -Q 4 -t 60
	```
	For futher infomation you can do `$ python3 ping_logger.py --help` 
	
* ### iperf3 client  
	Measure connection thoughtput from client side.  
	Syntax : `python3 iperf3_client_logger.py [options like origin iperf3 options]`  
	Example:

	```
	$ python3 iperf3_client_logger.py -c 192.168.0.50 -t 0 -b 5M -p 5202 -R
	```
	
	For futher infomation you can  `$ python3 iperf3_client_logger.py --help`   

* ### iperf3 server
	Measure connection thoughtput from server side.  
	Syntax : `python3 iperf3_server_logger.py [options like origin iperf3 options]`  
	Example:

	```
	$ python3 iperf3_server_logger.py -s 
	```
	
	For futher infomation you can do  `$ python3 iperf3_logger.py --help`   

* ### resources usage monitor
	Log basic resources usage of server. (linux only)   
	Syntax : `python3 resources_logger.py`  
	example:  
	
	```
	$ python3 resources_logger.py
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
	'line_notify_token': {
		(label): (your line notify token)
}
```
  
## Screenshot
### Chart from Grafana
![alt text](https://github.com/balao1312/amarisoft_test_logger/blob/master/alogger.png?raw=true)


### Watchdog Running
![alt text](https://github.com/balao1312/amarisoft_test_logger/blob/master/watchdogex.png?raw=true)
