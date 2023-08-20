#!/usr/bin/python3

import subprocess
import shlex
import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger
import argparse
import threading
import requests


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

        self.log_file = self.log_folder.joinpath(
            f'log_ping_{datetime.now().date()}')

    @property
    def platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result
    
    @property
    def with_internet(self):
        try:
            response = requests.get("https://google.com", timeout=5)
            return True
        except requests.ConnectionError:
            return False  
        
    def check_notify_msg_and_send(self):
        while True:
            # check internet first, assume ok
            if not self.with_internet:
                sleep(5)
                continue
            # print(self.unsent_notify)
            if self.unsent_notify:
                for each_msg in self.unsent_notify:
                    if self.send_line_notify('balao', each_msg):
                        continue
                    self.unsent_notify.remove(each_msg)

    def run(self):
        # start notify check on background
        thread_check_notify = threading.Thread(target=self.check_notify_msg_and_send, args=([]))
        thread_check_notify.start()

        if self.platform == 'Darwin':
            tos_option_string = '-z '
            exec_secs_string = f' -t {self.exec_secs} ' if self.exec_secs else ''
            show_anyway_string = ''
        elif self.platform == 'Linux':
            tos_option_string = '-Q '
            show_anyway_string = '-O '
            exec_secs_string = f'-c {self.exec_secs} ' if self.exec_secs else ''

        interval_string = f'-i {self.interval}'

        cmd = f'ping {show_anyway_string}{self.ip} {tos_option_string}{self.tos} {exec_secs_string}{interval_string}'
        print(f'==> cmd send: {cmd}\n')
        process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)

        count = 0
        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break

            if output:
                line = output.strip().decode('utf8')
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    latency = float(
                        list(filter(None, line.split(' ')))[6][5:10])
                    count += 1
                    print(
                        f'{count}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, dst:{self.ip}, tos: {self.tos}, label: {self.label}, latency: {latency} ms')

                    data = {
                        'measurement': 'ping',
                        'tags': {
                            'tos': self.tos,
                            'label': self.label
                        },
                        'time': record_time,
                        'fields': {'RTT': latency}
                    }
                    self.logging_with_buffer(data)

                    # for notify
                    # reset to 0, for only 5 secs to start notify if disconnect happens again
                    self.ping_no_return_count = 0

                    # notify for the come back of connection
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, Connection restored.'
                    if self.is_disconnected:
                        self.unsent_notify.append(msg)
                        self.is_disconnected = False

                    if self.notify_cap and latency > self.notify_cap:
                        msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\ngot a RTT from {self.ip} greater than {self.notify_cap} ms.\nvalue: {latency} ms.\nSeq: {count}'
                        thread_1 = threading.Thread(
                            target=self.send_line_notify, args=('balao', msg))
                        thread_1.start()

                except (ValueError, IndexError):
                    # deal with no connection
                    if 'no answer' in line:   
                        self.is_disconnected = True
                        self.ping_no_return_count += 1
                        print('.', end='')

                    if self.ping_no_return_count > 5:
                        print('\n==> ICMP packets are not returned. Maybe the connection is lost.')

                        # Send line notify and deal with if there is no internet
                        msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, No connection.'
                        if self.send_line_notify('balao', msg):
                            self.unsent_notify.append(msg)

                        # if stay disconnected, will notify again after 1hr
                        self.ping_no_return_count = -3595
                            # SElf.line_msg_unsent.append(f'{datetime.now()} Connection lost.')
                            # self.send_attempt += 1
                            # print(f'==> Notify send attempt for {self.send_attempt} times failed, store to buffer for trying larer.\n')
                            # print(self.line_msg_unsent)

                # except Exception as e:
                    # print(f'==> error: {e.__class__} {e}')

        self.clean_buffer_and_send()


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
    parser.add_argument('-i', '--interval', default=1, type=float,
                        help='interval between packets')
    parser.add_argument('-l', '--label', metavar='', default='none', type=str,
                        help='data label')

    args = parser.parse_args()

    logger = Ping_logger(args.host, args.tos, args.exec_secs,
                         args.notify_cap, args.interval, args.label)
    print(
        f'==> start pinging : {args.host}, tos: {args.tos}, duration: {args.exec_secs} secs\n')

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
    except Exception as e:
        print(f'==> error: {e.__class__} {e}')
