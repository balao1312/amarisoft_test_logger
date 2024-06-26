#!/usr/bin/python3

import subprocess
import sys
import os
from time import sleep
from datetime import datetime
from datetime import timedelta
from copy import copy
from amari_logger import Amari_logger
import argparse
import pexpect
import statistics
import threading
import logging


class Ping_logger(Amari_logger):

    def __init__(self, ip, tos, exec_secs, notify_when_disconnected, notify_cap, interval, label, project_field_name, dont_send_to_db, notify_dst):
        super().__init__()
        self.ip = ip
        self.tos = tos
        self.exec_secs = exec_secs
        self.notify_when_disconnected = notify_when_disconnected
        self.notify_cap = notify_cap
        self.interval = interval
        self.label = label
        self.is_disconnected = False
        self.project_field_name = project_field_name
        self.all_latency_values = []
        self.dont_send_to_db = dont_send_to_db
        self.notify_dst = notify_dst

        self.display_all_option()
        self.validate_notify_dst()

        # start notify check on background after child process is established if notify function is on
        if self.notify_when_disconnected or self.notify_cap > 0:
            self.thread_check_unsend_line_notify = threading.Thread(
                target=self.check_unsend_line_notify_and_try_send, args=([]))
            self.thread_check_unsend_line_notify.start()

    def turn_to_form(self, a, b):
        return f'| {a:<30}| {b:<85}|\n{"-" * 120}'

    def display_all_option(self):
        print('\n==> Tool related args:')
        print('-' * 120)
        print(self.turn_to_form('influxdb database', self.influxdb_dbname))
        print(self.turn_to_form('send disconnect nofify',
              str(bool(self.notify_when_disconnected))))
        print(self.turn_to_form(
            'latency cap to notify (ms)', self.notify_cap))
        print(self.turn_to_form('send data to db',
              str(bool(not self.dont_send_to_db))))
        print(self.turn_to_form('data label in db', self.label))
        print(self.turn_to_form('project field name', self.project_field_name))
        print(self.turn_to_form('notify destination', self.notify_dst))

    def validate_notify_dst(self):
        if self.can_send_line_notify:
            if not self.notify_dst:
                print(
                    f'==> Waring: Notify destination is not set, notify function is disabled.')
                self.can_send_line_notify = False
                return
            if not self.notify_dst in self.line_notify_dsts:
                print(
                    f'\n==> Notify destination "{self.notify_dst}" is not valid, notify function is disabled.\n')
                self.can_send_line_notify = False
                return

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_ping_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_ping_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')
        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    @property
    def platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result

    def parse_args_to_string(self):
        if self.platform == 'Darwin':
            tos_option_string = '-z'
            show_anyway_string = ''
            self.prompt_when_no_reply = 'Request timeout'
        elif self.platform == 'Linux':
            tos_option_string = '-Q'
            show_anyway_string = '-O '
            self.prompt_when_no_reply = 'no answer'

        exec_secs_string = f'-c {self.exec_secs} ' if self.exec_secs else ''
        interval_string = f'-i {self.interval}'

        self.cmd = f'ping {show_anyway_string}{self.ip} '\
                   f'{tos_option_string} '\
                   f'{self.tos} '\
                   f'{exec_secs_string}'\
                   f'{interval_string}'

        print(f'==> cmd send: \n\t\t{self.cmd}\n')
        self.stdout_log_object.write(f'ping cmd: {self.cmd}\n{"-"*80}\n')

    def gen_influx_format(self, record_time, latency):
        return {
            'measurement': 'ping',
            'tags': {
                'tos': self.tos,
                'label': self.label
            },
            'time': record_time,
            'fields': {'RTT': latency}
        }

    def gen_notify_format(self, msg):
        return {
            'project_field_name': self.project_field_name,
            'dst': 'balao',
            'msg': msg
        }

    def check_if_latency_higher_than_criteria(self, latency, seq_counter):
        if self.notify_cap and latency > self.notify_cap:
            msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'\
                f'got a RTT value from {self.ip} higher than {self.notify_cap} ms.\n'\
                f'value: {latency} ms.\nSeq: {seq_counter}'
            syslog_msg = f'got a RTT value from {self.ip} higher than {self.notify_cap} ms. value: {latency} ms. Seq: {seq_counter}'
            logging.warning(f"[{__class__.__name__}] {syslog_msg}")
            self.validate_to_send_notify(msg)

    def show_every_sec_result(self, counter, latency):
        msg = f'{counter}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, '\
            f'dst: {self.ip}, '\
            f'label: {self.label}, '\
            f'latency: {latency} ms'
        print(msg)

    def write_summary_to_stdout_file(self):
        '''
        --- 8.8.8.8 ping statistics ---
        5 packets transmitted, 5 received, 0% packet loss, time 4074ms
        rtt min/avg/max/mdev = 0.729/0.770/0.909/0.071 ms
        '''

        # avoid error when ctrlc at beginning confirm stage
        try:
            self.seq_counter
        except:
            return

        lost_rate = ((self.seq_counter - len(self.all_latency_values)
                      ) / self.seq_counter) * 100
        summary_min = min(self.all_latency_values)
        summary_max = max(self.all_latency_values)
        summary_avg = sum(self.all_latency_values) / \
            len(self.all_latency_values)

        summary_string = f'''
--- {self.ip} ping statistics ---
{self.seq_counter} packets transmitted, {len(self.all_latency_values)} received, {lost_rate:.4f}% packet loss
rtt min/avg/max/mdev = {summary_min}/{summary_avg:.3f}/{summary_max}/{statistics.pstdev(self.all_latency_values):.3f} ms
'''
        print(summary_string)
        with open(self.stdout_log_file, 'a') as f:
            f.write(summary_string)

    def send_to_db_on_demend(self, record_time, latency):
        if not self.dont_send_to_db:
            data = self.gen_influx_format(record_time, latency)
            self.logging_with_buffer(data)
        return

    def process_with_lines_dont_contain_latency(self, line):
        # deal with no reply
        if self.prompt_when_no_reply in line:
            self.ping_no_return_count += 1
            self.seq_counter += 1
            print('.', end='')

        # if more than 5 packet lost back to back,than consider it disconnected.
        if self.ping_no_return_count >= 5:
            self.is_disconnected = True
            print(
                f'\n==> ICMP packets are not returned. Target IP: {self.ip} cannot be reached.')
            syslog_msg = f'ICMP packets are not returned. Target IP: {self.ip} cannot be reached.'
            logging.warning(f"[{__class__.__name__}] {syslog_msg}")

            # Send line notify
            if self.notify_when_disconnected:
                delta = timedelta(seconds=-5)
                msg = f'[BAD] {(datetime.now()+delta).strftime("%Y-%m-%d %H:%M:%S")}\ntarget IP {self.ip} cannot be reached.'
                self.validate_to_send_notify(msg)

            # if stay disconnected, will notify again after 1hr
            self.ping_no_return_count = -3596

    def validate_to_send_notify(self, msg):
        if self.can_send_line_notify:
            self.unsend_line_notify_queue.put(self.gen_notify_format(msg))
            logging.info(
                f'[{__class__.__name__}] put a line notification to unsend_notification_queue.')
        return

    def run(self):
        self.refresh_log_file()
        self.parse_args_to_string()
        if input('Please confirm info above and press enter to continue.\n') != '':
            return

        logging.info(f'[{__class__.__name__}] start a ping session. Target IP: {self.ip}')
        self.child = pexpect.spawnu(self.cmd, timeout=10,
                                    logfile=self.stdout_log_object)

        self.ping_no_return_count = 0
        self.seq_counter = 0
        while True:
            try:
                self.child.expect('\n')
            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                self.stdout_log_object.close()
                break

            line = self.child.before
            try:
                latency = float(
                    list(filter(None, line.split(' ')))[6][5:10])
            except (ValueError, IndexError):
                self.process_with_lines_dont_contain_latency(line)
                continue

            record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            self.seq_counter += 1

            self.show_every_sec_result(self.seq_counter, latency)
            self.send_to_db_on_demend(record_time, latency)
            self.all_latency_values.append(latency)
            self.check_if_latency_higher_than_criteria(
                latency, self.seq_counter)

            # for notify, successful ICMP reply reset counter to 0
            self.ping_no_return_count = 0

            # notify for the come back of connection and toggle is_disconnected
            if self.is_disconnected and self.notify_when_disconnected:
                msg = f'[GOOD] {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{self.ip} can be reached again. :)'
                self.validate_to_send_notify(msg)
                self.is_disconnected = False

        self.stdout_log_object.close()
        self.clean_buffer_and_send()
        self.child.close()
        self.number_of_instances -= 1
        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--host', required=True, metavar='',
                        type=str, help='destination ip')
    parser.add_argument('-Q', '--tos', default=0, type=int, metavar='',
                        help='type of service value')
    parser.add_argument('-t', '--exec_secs', default=0, type=int, metavar='',
                        help='time duration (secs)')
    parser.add_argument('-N', '--notify_cap', default=0, type=int, metavar='',
                        help='latency value cap to notify (millisecs)')
    parser.add_argument('-i', '--interval', default=1, type=int, metavar='',
                        help='interval between packets')
    parser.add_argument('-l', '--label', default='none', type=str, metavar='',
                        help='record label in db')
    parser.add_argument('-F', '--project_field_name', default='', type=str, metavar='',
                        help='project field name for notify lable')
    parser.add_argument('-n', '--notify_when_disconnected', action="store_true",
                        help='send notify if target cannot be reached.')
    parser.add_argument('-U', '--dont_send_to_db', action="store_true",
                        help='disable sending record to db')
    parser.add_argument('-D', '--notify_dst', metavar='', default='', type=str,
                        help='line notify send destination')

    args = parser.parse_args()

    ping_logger = Ping_logger(
        args.host,
        args.tos,
        args.exec_secs,
        args.notify_when_disconnected,
        args.notify_cap,
        args.interval,
        args.label,
        args.project_field_name,
        args.dont_send_to_db,
        args.notify_dst
    )

    try:
        ping_logger.run()
    except KeyboardInterrupt:
        with open(ping_logger.stdout_log_file, 'a') as f:
            f.write('==> Got Ctrl+C.\n')
        ping_logger.write_summary_to_stdout_file()
        ping_logger.stdout_log_object.close()
        ping_logger.clean_buffer_and_send()
        print('\n==> Got Ctrl+C.\n')
        sleep(0.1)

        # try send data in buffer before close, timeout can be set in config.py
        max_sec_count = ping_logger.db_retries * ping_logger.db_timeout
        countdown = copy(max_sec_count)
        while ping_logger.is_in_sending_to_db_session:
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
