from amari_logger import Amari_logger
import subprocess
import shlex
import datetime
import pathlib
import re
import sys
import time
import os
from copy import copy
from config import config


class ros2_logger(Amari_logger):
    log_temp_plc = {}
    log_temp_ue = {}
    interval = 1
    buffer = datetime.timedelta(seconds=1)

    def __init__(self):
        super().__init__()

        self.log_file = self.log_folder.joinpath(
            f'log_ros2_{datetime.datetime.now().date()}')

    def parse_and_send_data(self, dict, tag):
        keys_to_delete = []
        for time_string, value in dict.items():
            time_object = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.utcnow() - time_object > self.buffer:
                value = sorted(value)
                print(f'{time_string}, {tag} alive:', value)

                # total alive count
                data = {
                    'measurement': 'ros2_log',
                    'tags': {'column': tag},
                    'time': time_string,
                    'fields': {f'total_{tag}_alive': len(value)}
                }
                self.logging_with_buffer(data)

                # convert to string for logging which are ailve
                string_to_send = ''
                for each in value:
                    string_to_send += each
                    if each != value[-1]:
                        string_to_send += ', '
                        
                data = {
                    'measurement': 'ros2_log',
                    'tags': {'column': tag},
                    'time': time_string,
                    'fields': {f'{tag}_alive' : string_to_send}
                }
                self.logging_with_buffer(data)

                keys_to_delete.append(time_string)
 
        for each in keys_to_delete:
            del dict[each]

    def run(self):
        # use python subprocess to start linux command and monitor standout
        process = subprocess.Popen(shlex.split(
            f'ros2 topic echo /pub'), shell=False, stdout=subprocess.PIPE)
            # f'python3 -u basic_listener.py'), shell=False, stdout=subprocess.PIPE)

        # use python dictionary to record which column value are at the same time
        # (due to python subprocess can only read ONE line in standout)
        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break
            if output:
                line = output.strip().decode('utf8')
                ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                words_in_bracket = re.compile(r'\[(.*?)\]')
                # get data in [ ]
                result = re.findall(words_in_bracket, line)
                if result and len(result[0]) > 1:
                    data_set = result[0].split(', ')
                    # target the "data:[..........]"
                    if int(data_set[3]) > 0:
                        try:
                            # data_set[3] = station_id
                            self.log_temp_plc[ts].add(data_set[3])
                        except:
                            self.log_temp_plc[ts] = set((data_set[3],))

                    if data_set[2] in ['108', '110', '112', '114']:
                        try:
                            self.log_temp_ue[ts].add(data_set[2])
                        except:
                            self.log_temp_ue[ts] = set((data_set[2],))

                # check periodically
                if datetime.datetime.now().second % self.interval == 0:
                    self.parse_and_send_data(self.log_temp_plc, 'plc') 
                    self.parse_and_send_data(self.log_temp_ue, 'ue') 


if __name__ == '__main__':
    logger = ros2_logger()
    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer()
        time.sleep(0.1)  # for avoiding the bug I cannot figure out
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
        print(f'==> error: {e.__class__} {e}')
