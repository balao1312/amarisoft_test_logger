#!/usr/bin/python3

# log for each station status separately

from amari_logger import Amari_logger
import subprocess
import shlex
import datetime
import re
import sys
import time
import os
import requests
from copy import copy
from config import config


class ros2_logger(Amari_logger):
    log_temp_plc = {}
    log_temp_ue = {}
    interval = 1
    buffer = datetime.timedelta(minutes=1)

    last_value = {}
    token = 'xrAUKB7KDmFh0CC97D1hgMl7NDNRimXK9GDF7SJOTFw'  # anest line group
    # token = '2unn268Rs1CkJ5JWGApbmwCPEB9qwSldVV5NNmukbFo' # balao test

    def __init__(self):
        super().__init__()

        self.log_file = self.log_folder.joinpath(
            f'log_ros2_{datetime.datetime.now().date()}')

    def lineNotifyMessage(self, line_token, msg):
        line_headers = {
            "Authorization": "Bearer " + line_token,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {'message': msg}
        r = requests.post("https://notify-api.line.me/api/notify",
                          headers=line_headers, params=payload)
        return r.status_code

    def show_on_off(self, last, now):
        text = ''
        for each in now:
            if each not in last:
                text += f'{each} is now up\n'

        for each in last:
            if each not in now:
                text += f'{each} is now down\n'
        return text

    def check_if_status_changed(self, tag, value):
        if tag not in self.last_value:
            return

        if not value == self.last_value[tag]:
            print(f'==> {tag} status change detected, trying to send notify...')
            try:
                self.notify_msg = f'\n{tag} status change detected:\n{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nbefore: {self.last_value[tag]}\nnow: {value}\nsummarized:\n{self.show_on_off(self.last_value[tag], value)}'
                self.lineNotifyMessage(self.token, self.notify_msg)
                print('==> notify sent.')
            except Exception as e:
                print(f'==> send line notify error: {e.__class__}, \n{e}')

            del self.last_value[tag]
            return

    def parse_and_send_data(self, dict, tag):
        keys_to_delete = []
        for time_string, value in dict.items():
            time_object = datetime.datetime.strptime(
                time_string, '%Y-%m-%d %H:%M')
            if datetime.datetime.utcnow() - time_object > self.buffer:
                value = sorted(value)
                print(f'{time_string}, {tag} alive:', value)

                # check if status changed
                self.check_if_status_changed(tag, value)
                self.last_value[tag] = value

                # a temp data pool
                data_pool = []

                # total alive count
                data = {
                    'measurement': 'ros2_log',
                    'tags': {'column': tag},
                    'time': time_string,
                    'fields': {f'total_{tag}_alive': len(value)}
                }
                data_pool.append(data)

                # convert to string for logging which are ailve
                string_to_send = ''
                for each in value:
                    string_to_send += each
                    if each != value[-1]:
                        string_to_send += ', '

                    # log each node separately
                    data = {
                        'measurement': 'ros2_log',
                        'tags': {'column': tag},
                        'time': time_string,
                        'fields': {each: 1}
                    }                   
                    data_pool.append(data)


                data = {
                    'measurement': 'ros2_log',
                    'tags': {'column': tag},
                    'time': time_string,
                    'fields': {f'{tag}_alive': string_to_send}
                }
                data_pool.append(data)
                
                for each in data_pool:
                    self.logging_with_buffer(each)

                keys_to_delete.append(time_string)

        for each in keys_to_delete:
            del dict[each]

    def run(self):
        # use python subprocess to start linux command and monitor standout
        cmd = 'ros2 topic echo /pub'
        # cmd = 'python3 -u basic_listener.py'

        print(f'==> cmd send: {cmd}')
        process = subprocess.Popen(shlex.split(
            cmd), shell=False, stdout=subprocess.PIPE)

        # use python dictionary to record which column value are at the same time
        # (due to python subprocess can only read ONE line in standout)
        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break
            if output:
                line = output.strip().decode('utf8')
                ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')
                words_in_bracket = re.compile(r'\[(.*?)\]')  # get data in [ ]
                result = re.findall(words_in_bracket, line)
                if result and len(result[0]) > 1:
                    data_set = result[0].split(', ')
                    if int(data_set[3]) > 0:
                        try:
                            self.log_temp_plc[ts].add(data_set[3])
                        except:
                            self.log_temp_plc[ts] = set((data_set[3],))

                    if data_set[2] in ['108', '110', '112', '114']:
                        try:
                            self.log_temp_ue[ts].add(data_set[2])
                        except:
                            self.log_temp_ue[ts] = set((data_set[2],))

                # check periodically
                if datetime.datetime.now().minute % self.interval == 0:
                    self.parse_and_send_data(self.log_temp_plc, 'plc')
                    self.parse_and_send_data(self.log_temp_ue, 'ue')


if __name__ == '__main__':
    logger = ros2_logger()
    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer_and_send()
        time.sleep(0.1)
        max_sec_count = logger.db_retries * logger.db_timeout
        countdown = copy(max_sec_count)
        while logger.is_sending:
            if countdown < max_sec_count:
                print(
                    f'==> waiting for process to end ... secs left max {countdown}')
            countdown -= 1
            time.sleep(1)
        try:
            print('\n==> Exited')
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f'==> main func error: {e.__class__} {e}')
