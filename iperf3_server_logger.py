#!/usr/bin/python3

import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger
import argparse
import re
import pexpect
import threading


class Iperf3_logger(Amari_logger):

    def __init__(self, port, parallel, notify, label, dont_send_to_db):
        super().__init__()
        self.port = port
        self.is_in_parallel_mode = parallel
        self.notify_when_terminated = notify
        self.label = label
        self.dont_send_to_db = dont_send_to_db

        # define RE patterns
        self.average_pattern = re.compile(r'.*(sender|receiver)')
        self.sum_parallel_pattern = re.compile(
            r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')
        self.standby_pattern = re.compile(r'Server listening')

        # iperf3: the client has terminated
        self.terminated_pattern = re.compile(r'iperf3:')

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_iperf3_server_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')

        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

        print(
            f'==> iperf3 stdout will be logged to: {self.stdout_log_file}.txt')

    def parse_args_to_string(self):
        self.cmd = f'iperf3 -s -p {self.port} -f m'

        print(f'==> cmd send: \n\n\t{self.cmd}\n')
        print(
            f'==> parallel mode: {self.is_in_parallel_mode}, ******* check this arg or the result would be wrong!')
        print(f'==> notify when terminated: {self.notify_when_terminated}')
        print(f'==> influxdb label used: {self.label}')
        self.stdout_log_object.write(f'iperf3 cmd: {self.cmd}\n{"-"*80}\n')

    def check_if_is_summary_and_show(self, line):
        if self.average_pattern.match(line):
            print(self.average_pattern.search(line).group(0))
            return True
        else:
            return False

    def gen_influx_format(self, record_time, mbps):
        return {
            'measurement': 'iperf3',
            'tags': {
                'label': self.label
            },
            'time': record_time,
            'fields': {'Mbps': mbps}
        }

    def run_iperf3_session(self):
        child = pexpect.spawnu(self.cmd, timeout=60,
                               logfile=self.stdout_log_object)
        zero_counter = 0
        counter = 0
        while True:
            try:
                child.expect('\n')
                line = child.before
                print(line)
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # detect session end and clean buffer
                if self.standby_pattern.match(line):
                    self.clean_buffer_and_send()

                # notify when terminated
                if self.terminated_pattern.match(line) and self.notify_when_terminated:
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{self.label}\n{line.strip()}.'
                    thread_1 = threading.Thread(
                        target=self.send_line_notify, args=('balao', msg))
                    thread_1.start()

                # check if in parallel mode
                # must be a better way, TODO
                if not self.is_in_parallel_mode:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    counter += 1
                else:
                    if not self.sum_parallel_pattern.search(line):
                        continue
                    else:
                        mbps = float(
                            self.sum_parallel_pattern.search(line).group(1))
                        counter += 1
                        # print(mbps)

                if self.check_if_is_summary_and_show(line):
                    continue

                if not self.dont_send_to_db:
                    data = self.gen_influx_format(record_time, mbps)
                    self.logging_with_buffer(data)

                if mbps == 0:
                    zero_counter += 1
                    if zero_counter == 180:
                        print(
                            '\n==> Can\'t get result from client for 3 mins, stopped.(Disconnecion may be the reason.)\n')
                        break
                else:
                    zero_counter = 0

            except pexpect.TIMEOUT as e:
                # print('==> pexpect timeout.')
                pass
            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                # print(f'==> Error: {e}')
                break
            except (ValueError, IndexError):
                # skip iperf stdout that DONT contain throughput lines
                pass
        self.clean_buffer_and_send()
        return

    def run(self):
        self.refresh_log_file()
        self.parse_args_to_string()
        # TODO show a table of args to let user confirm
        while True:
            self.run_iperf3_session()
            sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', metavar='', default=5201, type=int,
                        help='iperf server port')
    parser.add_argument('-P', '--parallel', action="store_true",
                        help='detect client in parallel mode')
    parser.add_argument('-n', '--notify', action="store_true",
                        help='notify when terminated')
    parser.add_argument('-l', '--label', metavar='', default='', type=str,
                        help='data label')
    parser.add_argument('-U', '--dont_send_to_db', action="store_true",
                        help='disable sending record to db')

    args = parser.parse_args()

    logger = Iperf3_logger(
        port=args.port,
        parallel=args.parallel,
        notify=args.notify,
        label=args.label,
        dont_send_to_db=args.dont_send_to_db
    )

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer_and_send()
        sleep(0.1)
        max_sec_count = logger.db_retries * logger.db_timeout
        countdown = copy(max_sec_count)
        while logger.is_sending:
            if countdown < max_sec_count:
                print(
                    f'==> waiting for process to end ... secs left max {countdown}')
            countdown -= 1
            sleep(1)
        try:
            print('\n==> Exited')
            sys.exit(0)
        except SystemExit:
            os._exit(0)
