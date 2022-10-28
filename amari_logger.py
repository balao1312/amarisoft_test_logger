from pathlib import Path
import threading
import pickle
import json
import time
import requests
import sys

from config import config


class Amari_logger:

    is_send_to_db = True

    # check if python influx module installed
    try:
        from influxdb import InfluxDBClient
    except ModuleNotFoundError:
        print('\n==> module influxdb is not found, send to db function is disabled.')
        time.sleep(2)
        is_send_to_db = False

    # check if credential exists
    try:
        from credential import db_config
        influxdb_ip = db_config['influxdb_ip']
        influxdb_port = db_config['influxdb_port']
        influxdb_username = db_config['influxdb_username']
        influxdb_password = db_config['influxdb_password']
        influxdb_dbname = db_config['influxdb_dbname']
    except (NameError, ImportError, KeyError) as e:
        print('\n==> credential.py is not found or db_config format incorrect, send to db function is disabled.')
        time.sleep(2)
        is_send_to_db = False

    try:
        line_notify_token = db_config['line_notify_token']
    except (NameError, ImportError, KeyError) as e:
        print('\n==> Line notify token is not found in credential.py, notify function is disabled.')
        time.sleep(2)

    def __init__(self):

        self.log_folder = Path.cwd().joinpath('logs')
        if not self.log_folder.exists():
            self.log_folder.mkdir()

        self.send_fail_file = self.log_folder.joinpath('send_fail')

        self.db_timeout = config['db_connect_timeout']
        self.db_retries = config['db_connect_retries']
        self.number_of_buffer = config['number_of_buffer']

        self.data_pool = []
        self.is_sending = False

        if self.is_send_to_db:
            print(f'\n==> database used in influxdb: {self.influxdb_dbname}')
            time.sleep(2)

    def send_line_notify(self, dst, msg):
        def lineNotifyMessage(line_token, msg):
            line_headers = {
                "Authorization": "Bearer " + line_token,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            payload = {'message': msg}
            r = requests.post("https://notify-api.line.me/api/notify",
                              headers=line_headers, params=payload)
            return r.status_code

        if not self.line_notify_token:
            return

        token = self.line_notify_token[dst]

        print('==> trying send notify ...')
        try:
            lineNotifyMessage(token, msg)
            print('==> notify sent.')
        except Exception as e:
            print(
                f'==> func: {sys._getframe().f_code.co_name} error: {e.__class__} {e}')

    def write_to_file(self):
        with open(self.log_file, 'a') as f:
            for each in self.data_pool:
                f.write(f'{json.dumps(each)}\n')
        print(f'==> records saved to log file: {self.log_file}. ')

    def send_to_influx(self, influx_format_list):
        try:
            db_cli = self.InfluxDBClient(
                self.influxdb_ip,
                self.influxdb_port,
                self.influxdb_username,
                self.influxdb_password,
                self.influxdb_dbname,
                timeout=self.db_timeout,
                retries=self.db_retries)
        except Exception as e:
            print(f'==> can not establish connection to DB.')
            print(f'==> error: {e.__class__} {e}')
            return

        # add up those unsend_data if exists
        if self.send_fail_file.exists():
            with open(self.send_fail_file, 'rb') as f:
                unsend_data = pickle.load(f)
            influx_format_list += unsend_data

            self.send_fail_file.unlink()

        try:
            print('==> trying to send to db ...')
            self.is_sending = True
            db_cli.write_points(influx_format_list)
            print(f'==> {len(influx_format_list)} records sent.')
            self.is_sending = False

        except Exception as e:
            print('==> send failed. put data to send_fail.')
            print(f'==> error: {e.__class__} {e}')

            # check if there is new unsend data generate by other thread
            if self.send_fail_file.exists():
                print('==> found previous unsent data.')
                with open(self.send_fail_file, 'rb') as f:
                    prev_data = pickle.load(f)
                influx_format_list += prev_data

            with open(self.send_fail_file, 'wb') as f:
                pickle.dump(influx_format_list, f)
            self.is_sending = False

    def data_landing(self):
        self.write_to_file()
        if self.is_send_to_db == True:
            thread_1 = threading.Thread(
                target=self.send_to_influx, args=(self.data_pool,))
            thread_1.start()
        self.data_pool = []

    def logging_with_buffer(self, data):
        self.data_pool.append(data)
        if len(self.data_pool) >= self.number_of_buffer:
            self.data_landing()

    def clean_buffer_and_send(self):
        if self.data_pool:
            self.data_landing()

    def parse_single_file(self, file):
        print(f'==> parsing file: {file}')
        try:
            with open(file, 'r') as f:
                string_data_list = f.readlines()
        except UnicodeDecodeError as e:
            print(f'==> \tskipping file {file}:')
            print(f'==> \t\t{e.__class__}, {e}')
            return []

        data_list = []
        for nol, line in enumerate(string_data_list, start=1):
            try:
                data_list.append(json.loads(line))
            except Exception as e:
                print(f'==> \tskipping line {nol}:')
                print(f'==> \t\t{e.__class__}, {e}')
                continue
        print('==> done.\n')
        return data_list

    def parse_and_send(self, f_object):
        data_to_send = []
        if f_object.is_dir():
            for each_file in [file for file in f_object.iterdir() if file.name[:3] == 'log']:
                data_to_send += self.parse_single_file(each_file)
        else:
            data_to_send += self.parse_single_file(f_object)

        self.send_to_influx(data_to_send)
