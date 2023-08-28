#!/usr/bin/python3

import subprocess
import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger
import argparse
import threading
import pexpect
import shlex


class Ping_logger(Amari_logger):

    def __init__(self, ip, tos, exec_secs, notify, notify_cap, interval, label, project_field_name):
        super().__init__()
        self.ip = ip
        self.tos = tos
        self.exec_secs = exec_secs
        self.will_send_notify = notify
        self.notify_cap = notify_cap
        self.interval = interval
        self.label = label
        self.unsent_notify = []
        self.ping_no_return_count = 0
        self.is_disconnected = False
        self.project_field_name = project_field_name

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_ping_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_ping_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')
        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

        print(
            f'==> ping stdout will be logged to: {self.stdout_log_file}.txt')

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

        print(f'==> influxdb label used: {self.label}')
        print(f'==> send line notify: {self.will_send_notify}')
        if self.notify_cap:
            print(
                f'==> send notify when latency is higher than: {self.notify_cap} ms')
        if self.project_field_name:
            print(f'==> project field name: {self.project_field_name}')
        print(f'==> cmd send: \n\t\t{self.cmd}\n')
        print('-'*80)
        self.stdout_log_object.write(f'ping cmd: {self.cmd}\n{"-"*80}\n')

    def check_unsend_notify_and_try_send(self):
        '''
        All notify msg will be add to self.unsend_notify. This func will check if any and try to send.
        '''
        while True:
            if self.child.closed:
                return
            if not self.is_with_internet:
                sleep(5)
                continue
            if self.unsent_notify:
                print(
                    f'==> Find {len(self.unsent_notify)} unsend notify before, try sending...')
                for each_msg in self.unsent_notify:
                    msg_with_projectf_field_name = f'\n[{self.project_field_name}]\n{each_msg}'
                    if not self.send_line_notify('balao', msg_with_projectf_field_name):
                        self.unsent_notify.remove(each_msg)
                    sleep(1)
            sleep(5)

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

    def check_if_latency_higher_than_criteria(self, latency, counter):
        if self.notify_cap and latency > self.notify_cap:
            msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'\
                f'got a RTT value from {self.ip} higher than {self.notify_cap} ms.\n'\
                f'value: {latency} ms.\nSeq: {counter}'
            self.unsent_notify.append(msg)
    
    def show_every_sec_result(self, counter, latency):
        msg = f'{counter}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, '\
        f'dst: {self.ip}, '\
        f'label: {self.label}, '\
        f'latency: {latency} ms'
        print(msg)

    def run(self):
        self.refresh_log_file()
        self.parse_args_to_string()
        if input('Please confirm info above and press enter to continue.\n') != '':
            return

        self.child = pexpect.spawnu(self.cmd, timeout=10,
                                    logfile=self.stdout_log_object)

        # start notify check on background after child process is established
        if self.will_send_notify:
            self.thread_check_notify = threading.Thread(
                target=self.check_unsend_notify_and_try_send, args=([]))
            self.thread_check_notify.start()

        counter = 0
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
                # deal with no reply
                if self.prompt_when_no_reply in line:
                    self.ping_no_return_count += 1
                    counter += 1
                    print('.', end='')

                # if more than 5 packet lost back to back,than consider it disconnected.
                if self.ping_no_return_count > 5:
                    self.is_disconnected = True
                    print(
                        f'\n==> ICMP packets are not returned. Target IP: {self.ip} cannot be reached. ')

                    # Send line notify
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, target IP {self.ip} cannot be reached.'
                    self.unsent_notify.append(msg)

                    # if stay disconnected, will notify again after 1hr
                    self.ping_no_return_count = -3595
                continue

            record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            counter += 1
            
            self.show_every_sec_result(counter, latency)

            data = self.gen_influx_format(record_time, latency)
            self.logging_with_buffer(data)

            # for notify, reset to 0, for only 5 secs to start notify if disconnect happens again
            self.ping_no_return_count = 0

            # notify for the come back of connection
            if self.is_disconnected:
                msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {self.ip} can be reached again. :)'
                self.unsent_notify.append(msg)
                self.is_disconnected = False

            self.check_if_latency_higher_than_criteria(latency, counter)

        self.clean_buffer_and_send()
        self.child.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--host', required=True,
                        type=str, help='destination ip')
    parser.add_argument('-Q', '--tos', default=0, type=int,
                        help='type of service value')
    parser.add_argument('-t', '--exec_secs', default=0, type=int,
                        help='time duration (secs)')
    parser.add_argument('-n', '--notify', action="store_true",
                        help='send notify if target cannot be reached or latency is higher than user defined')
    parser.add_argument('-N', '--notify_cap', default=0, type=int,
                        help='latency value cap to notify (millisecs)')
    parser.add_argument('-i', '--interval', default=1, type=int,
                        help='interval between packets')
    parser.add_argument('-l', '--label', metavar='', default='none', type=str,
                        help='data label')
    parser.add_argument('-F', '--project_field_name', metavar='', default='', type=str,
                        help='data label')

    args = parser.parse_args()

    logger = Ping_logger(args.host, args.tos, args.exec_secs, args.notify,
                         args.notify_cap, args.interval, args.label, args.project_field_name)

    try:
        logger.run()
    except KeyboardInterrupt:
        with open(logger.stdout_log_file, 'a') as f:
            f.write('==> Get Ctrl+C.\n')
        logger.stdout_log_object.close()

        # TODO: show statistics
        print('\n==> Interrupted.\n')
        logger.clean_buffer_and_send()
        sleep(0.1)

        # try send data in buffer before close, timeout can be set in config.py
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
