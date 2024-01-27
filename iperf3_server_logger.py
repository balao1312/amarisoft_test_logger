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
import signal


class Iperf3_logger(Amari_logger):

    def __init__(self, port, parallel, notify_when_terminated, label, dont_send_to_db, project_field_name, notify_dst):
        super().__init__()
        self.port = port
        self.is_in_parallel_mode = parallel
        self.notify_when_terminated = notify_when_terminated
        self.label = label
        self.project_field_name = project_field_name
        self.dont_send_to_db = dont_send_to_db
        self.notify_dst = notify_dst

        # define RE patterns
        self.average_pattern = re.compile(r'.*(sender|receiver)')
        self.single_thread_mode_throughput_pattern = re.compile(
            r'.*\ ([0-9.]*)\ Mbits\/sec')
        self.multi_threads_mode_throughput_pattern = re.compile(
            r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')
        self.standby_pattern = re.compile(r'Server listening')
        # the stdout when client disconnected is "iperf3: the client has terminated"
        # char after iperf3: is considered not as stdout so pexpect wont catch that. capture iperf3: is workaround.
        self.terminated_pattern = re.compile(r'iperf3:')

        self.parse_args_to_string()
        self.display_all_option()
        self.validate_notify_dst()

    def display_all_option(self):
        print('\n==> Tool related args:')
        print('-' * 120)
        print(self.turn_to_form('influxdb database', self.influxdb_dbname))
        print(self.turn_to_form('send data to db',
              str(bool(not self.dont_send_to_db))))
        print(self.turn_to_form('data label in db', self.label))
        print(self.turn_to_form('project field name', self.project_field_name))
        print(self.turn_to_form('notify when terminated',
              str(bool(self.notify_when_terminated))))
        print(self.turn_to_form('parallel mode',
              str(bool(self.is_in_parallel_mode))))
        print(self.turn_to_form('notify destination', self.notify_dst))
        print('==> !!!!!!!!!!!!!!!!! check parallel mode arg or the result would be wrong!')
        print(f'==> original cmd send: \n\n\t{self.cmd}\n')
    
    def validate_notify_dst(self): 
        if self.can_send_line_notify:
            if not self.notify_dst:
                print(f'==> Waring: Notify destination is not set.')
                return
            if not self.notify_dst in self.line_notify_dsts:
                print(f'\n==> Notify destination "{self.notify_dst}" is not valid, notify function is disabled.\n')
                self.can_send_line_notify = False

    def turn_to_form(self, a, b):
        return f'| {a:<30}| {b:<85}|\n{"-" * 120}'

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_iperf3_server_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')
        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"-"*80}\n')

    def parse_args_to_string(self):
        self.cmd = f'iperf3 -s -p {self.port} -f m'

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

    def gen_notify_format(self, msg):
        return {
            'project_field_name': self.project_field_name,
            'dst': self.notify_dst,
            'msg': msg
        }

    def notify_when_client_termainated_on_demand(self, line):
        if not self.can_send_line_notify:
            return
        if self.terminated_pattern.match(line) and self.notify_when_terminated:
            msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{line.strip()}.'
            self.unsend_line_notify_queue.put(self.gen_notify_format(msg))
        return

    def send_to_db_on_demend(self, record_time, mbps):
        if not self.dont_send_to_db:
            data = self.gen_influx_format(record_time, mbps)
            self.logging_with_buffer(data)
        return

    def check_if_is_disconnected(self, mbps):
        if mbps == 0:
            self.zero_counter += 1
            if self.zero_counter >= 180:
                print(
                    '\n==> Can\'t get result from server for 3 mins, session stopped.(Disconnecion may be the reason)\n')
                return True
        else:
            self.zero_counter = 0
            return False

    def run_iperf3_session(self):
        '''
        The idea is to show original iperf3 server stdout, so not showing counter every second.
        '''

        print('==> Start iperf3 server session...\n')
        self.refresh_log_file()
        sleep(1)

        child = pexpect.spawnu(self.cmd, timeout=10,
                               logfile=self.stdout_log_object)

        self.zero_counter = 0
        while True:
            try:
                child.expect('\n')
            except pexpect.exceptions.TIMEOUT as e:
                # pexpect child process cannot set timeout to infinity, workaround.
                continue
            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                break
            line = child.before
            print(line)
            record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # detect session end and clean buffer
            if self.standby_pattern.match(line):
                self.clean_buffer_and_send()

            self.notify_when_client_termainated_on_demand(line)

            # get throughput but check first if parallel number > 2
            if not self.is_in_parallel_mode:
                if not self.single_thread_mode_throughput_pattern.search(line):
                    continue
                mbps = float(
                    self.single_thread_mode_throughput_pattern.search(line).group(1))
            else:
                if not self.multi_threads_mode_throughput_pattern.search(line):
                    continue
                else:
                    mbps = float(
                        self.multi_threads_mode_throughput_pattern.search(line).group(1))

            if self.check_if_is_disconnected(mbps):
                break

            if self.check_if_is_summary_and_show(line):
                continue

            self.send_to_db_on_demend(record_time, mbps)

        self.stdout_log_object.close()
        self.clean_buffer_and_send()
        child.kill(signal.SIGINT)
        return

    def run(self):
        while True:
            self.run_iperf3_session()
            sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', metavar='', default=5201, type=int,
                        help='iperf server port')
    parser.add_argument('-P', '--parallel', action="store_true",
                        help='detect client in parallel mode')
    parser.add_argument('-n', '--notify_when_terminated', action="store_true",
                        help='notify when terminated')
    parser.add_argument('-l', '--label', metavar='', default='', type=str,
                        help='data label')
    parser.add_argument('-F', '--project_field_name', metavar='', default="", type=str,
                        help='Name of the project field')
    parser.add_argument('-U', '--dont_send_to_db', action="store_true",
                        help='disable sending record to db')
    parser.add_argument('-D', '--notify_dst', metavar='', default='', type=str,
                        help='line notify send destination')

    args = parser.parse_args()

    logger = Iperf3_logger(
        port=args.port,
        parallel=args.parallel,
        notify_when_terminated=args.notify_when_terminated,
        label=args.label,
        project_field_name=args.project_field_name,
        dont_send_to_db=args.dont_send_to_db,
        notify_dst=args.notify_dst
    )

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer_and_send()
        sleep(0.1)
        max_sec_count = logger.db_retries * logger.db_timeout
        countdown = copy(max_sec_count)
        while logger.is_in_sending_to_db_session:
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
