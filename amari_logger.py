from pathlib import Path
import threading
import pickle
import json
import time
import requests
import subprocess
import shlex
from time import sleep
import queue

from config import config


class Amari_logger:

    is_send_to_db = True

    # check if python influx module installed
    try:
        from influxdb import InfluxDBClient
    except ModuleNotFoundError:
        print('\n==> module influxdb is not found, send to db function is disabled.\n')
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
        influxdb_dbname = ''

    def __init__(self):
        self.log_folder = Path.cwd().joinpath('logs')
        if not self.log_folder.exists():
            self.log_folder.mkdir()

        self.send_fail_file = self.log_folder.joinpath('send_fail')
        self.db_timeout = config['db_connect_timeout']
        self.db_retries = config['db_connect_retries']
        self.number_of_buffer = config['number_of_buffer']
        self.data_pool = []
        self.is_in_sending_to_db_session = False
        self.can_send_line_notify = False
        self.unsend_line_notify_queue = queue.Queue()
        self.validate_notify_token()

        # start notify check on background after child process is established
        self.thread_check_unsend_line_notify = threading.Thread(
            target=self.check_unsend_line_notify_and_try_send, args=([]))
        self.thread_check_unsend_line_notify.start()

    def validate_notify_token(self):
        try:
            self.line_notify_dsts = self.db_config['line_notify_token']
            if len(self.line_notify_dsts) > 0:
                self.can_send_line_notify = True
            else:
                print(
                    '\n==> Line notify token is not found, notify function is disabled.')
                time.sleep(2)
        except (NameError, ImportError, KeyError) as e:
            print(
                '\n==> Line notify token is not found, notify function is disabled.')
            time.sleep(2)

    @property
    def platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result

    @property
    def is_with_internet(self):
        if self.platform == 'Darwin':
            cmd = 'ping -c 1 -W 2000 google.com'
        elif self.platform == 'Linux':
            cmd = 'ping -c 1 -W 2 google.com'
        result = subprocess.run(shlex.split(
            cmd), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if result.returncode:
            return False
        else:
            return True

    def send_line_notify(self, dst, msg):
        def lineNotifyMessage(line_token, msg):
            line_headers = {
                "Authorization": "Bearer " + line_token,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            payload = {'message': msg}

            retry_counter = 0
            while retry_counter < 3:
                r = requests.post("https://notify-api.line.me/api/notify",
                                  headers=line_headers, params=payload)
                if r.status_code == 200:
                    print('==> Line notify sent.')
                    return
                else:
                    retry_counter += 1
                    print(f'==> Send notify failed. attempt = {retry_counter}')
                    sleep(1)
            # if still send fail then put back to queue
            self.unsend_line_notify_queue.put(
                self.parse_line_msg_back_to_queue_object(line_token, msg))

        if not self.can_send_line_notify:
            return

        token = self.line_notify_dsts[dst]
        print('==> Trying send line notify...')

        self.thread_send_line_notify = threading.Thread(
            target=lineNotifyMessage, args=(token, msg))
        self.thread_send_line_notify.start()
        return

    def parse_line_msg_back_to_queue_object(self, line_token, str):
        '''
        Just for my obsessive-compulsive disorder.
        When line notify keep sending fail, notify need to be put back to unsend line notify queue,
        but the notify info has been concatenate to one long string.
        This function will parse it back to notify format designed.
        '''
        dst = list(self.line_notify_token.keys())[
            list(self.line_notify_token.values()).index(line_token)]
        project_field_name = str.split('\n')[1][1:-1]
        msg = '\n'.join(str.split('\n')[2:])
        return {
            'project_field_name': project_field_name,
            'dst': dst,
            'msg': msg
        }

    def check_unsend_line_notify_and_try_send(self):
        '''
        All notify msg will be add to self.unsend_line_notify_queue.
        This func will check if there is any and try to send.

        line notify data format: {
            'project_field_name':
            'dst':
            'msg':
        }
        '''
        while True:
            if not self.is_with_internet:
                sleep(5)
                continue
            try:
                notify = self.unsend_line_notify_queue.get(timeout=3)
                self.unsend_line_notify_queue.task_done()
                msg_string = f'\n[{notify["project_field_name"]}]\n{notify["msg"]}'
                self.send_line_notify(notify['dst'], msg_string)
            except queue.Empty as e:
                continue

            sleep(5)

    def write_to_file(self):
        with open(self.log_file, 'a') as f:
            for each in self.data_pool:
                f.write(f'{json.dumps(each)}\n')
        # print(f'==> records saved to log file: {self.log_file}. ')

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
            print('==> Trying to send records to db...')
            self.is_in_sending_to_db_session = True
            db_cli.write_points(influx_format_list)
            print(f'==> {len(influx_format_list)} records sent.')
            self.is_in_sending_to_db_session = False

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
            self.is_in_sending_to_db_session = False

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
