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
import requests
import pexpect
import signal


class Ping_logger(Amari_logger):

    def __init__(self, ip, tos, exec_secs, notify_cap, interval, label):
        super().__init__()
        self.ip = ip
        self.tos = tos
        self.exec_secs = exec_secs
        self.notify_cap = notify_cap
        self.interval = interval
        self.label = label
        self.unsent_notify = []
        self.ping_no_return_count = 0
        self.is_disconnected = False
        # self.is_send_notify_when_no_reply = False

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
        try:
            response = requests.get("https://google.com", timeout=5)
            return True
        except (requests.ConnectionError, requests.ReadTimeout):
            return False

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
        # TODO, add an option to toggle, now is always send
        # print(f'==> notify when terminated: {}')
        print(f'==> influxdb label used: {self.label}')
        print('-'*80)
        self.stdout_log_object.write(f'ping cmd: {self.cmd}\n{"-"*80}\n')

    def check_notify_msg_and_send(self):
        # TODO: send notify in another thread
        if not self.is_with_internet:
            return
        if self.unsent_notify:
            print(f'==> Find {len(self.unsent_notify)} unsend notify before, try sending...')
            for each_msg in self.unsent_notify:
                if not self.send_line_notify('balao', each_msg):
                    self.unsent_notify.remove(each_msg)
        return

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

    def run(self):
        # start notify check on background
        self.thread_check_notify = threading.Thread(
            target=self.check_notify_msg_and_send, args=([]))
        self.thread_check_notify.start()

        self.refresh_log_file()
        self.parse_args_to_string()
        sleep(1)

        self.child = pexpect.spawnu(self.cmd, timeout=10,
                                    logfile=self.stdout_log_object)
        counter = 0
        while True:
            try:
                self.child.expect('\n')
                line = self.child.before
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                latency = float(
                    list(filter(None, line.split(' ')))[6][5:10])
                counter += 1
                print(
                    f'{counter}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, dst:{self.ip}, tos: {self.tos}, label: {self.label}, latency: {latency} ms')

                data = self.gen_influx_format(record_time, latency)
                self.logging_with_buffer(data)

                # for notify, reset to 0, for only 5 secs to start notify if disconnect happens again
                self.ping_no_return_count = 0

                # notify for the come back of connection
                msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {self.ip} can be reached again. :)'
                if self.is_disconnected:
                    self.unsent_notify.append(msg)
                    self.is_disconnected = False

                # send notify when latency is higher then user defined
                # TODO: func it
                if self.notify_cap and latency > self.notify_cap:
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\ngot a RTT from {self.ip} greater than {self.notify_cap} ms.\nvalue: {latency} ms.\nSeq: {counter}'
                    thread_1 = threading.Thread(
                        target=self.send_line_notify, args=('balao', msg))
                    thread_1.start()
                
                self.check_notify_msg_and_send()

            except (ValueError, IndexError):
                # deal with no reply
                if self.prompt_when_no_reply in line:
                    self.ping_no_return_count += 1
                    print('.', end='')
                
                # if more than 5 packet lost back to back,than consider it disconnected.
                if self.ping_no_return_count > 5:
                    self.is_disconnected = True
                    print(
                        f'\n==> ICMP packets are not returned. Target IP:{self.ip} cannot be reached. ')

                    # Send line notify and deal with if there is no internet
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, 5G connection Lost! Cannot reach {self.ip}. Check connection!'
                    if self.send_line_notify('balao', msg):
                        self.unsent_notify.append(msg)

                    # if stay disconnected, will notify again after 1hr
                    self.ping_no_return_count = -3595
                    # SElf.line_msg_unsent.append(f'{datetime.now()} Connection lost.')
                    # self.send_attempt += 1
                    # print(f'==> Notify send attempt for {self.send_attempt} times failed, store to buffer for trying larer.\n')
                    # print(self.line_msg_unsent)
            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                # self.check_notify_msg_and_send()
                self.stdout_log_object.close()
                break
        self.clean_buffer_and_send()

        self.child.close()
        # self.thread_check_notify.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--host', required=True,
                        type=str, help='destination ip')
    parser.add_argument('-Q', '--tos', default=0, type=int,
                        help='type of service value')
    parser.add_argument('-t', '--exec_secs', default=0, type=int,
                        help='time duration (secs)')
    parser.add_argument('-n', '--notify_cap', default=0, type=int,
                        help='latency value cap to notify (millisecs)')
    parser.add_argument('-i', '--interval', default=1, type=int,
                        help='interval between packets')
    parser.add_argument('-l', '--label', metavar='', default='none', type=str,
                        help='data label')

    args = parser.parse_args()

    logger = Ping_logger(args.host, args.tos, args.exec_secs,
                         args.notify_cap, args.interval, args.label)

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
