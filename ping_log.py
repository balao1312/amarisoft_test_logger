#!/usr/bin/python3

import subprocess
import shlex
import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger


class Ping_logger(Amari_logger):

    def __init__(self, ip, tos):
        super().__init__()
        self.ip = ip
        self.tos = tos

        self.log_file = self.log_folder.joinpath(
            f'log_ping_{datetime.now().date()}')

    @property
    def platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result

    def run(self):
        if self.platform == 'Darwin':
            tos_option_string = '-z'
        elif self.platform == 'Linux':
            tos_option_string = '-Q'

        process = subprocess.Popen(shlex.split(
            f'ping {self.ip} {tos_option_string} {self.tos}'), stdout=subprocess.PIPE)

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
                    print(
                        f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, dst:{self.ip}, tos: {self.tos}, latency: {latency} ms')

                    data = {
                        'measurement': 'ping',
                        'tags': {'tos': self.tos},
                        'time': record_time,
                        'fields': {'RTT': latency}
                    }
                    self.logging_with_buffer(data)

                except (ValueError, IndexError):
                    pass
                except Exception as e:
                    print(f'==> error: {e.__class__} {e}')


if __name__ == '__main__':
    try:
        ip = sys.argv[1]
        tos = sys.argv[2]
    except:
        print('==> arg wrong, should be:\n python3 ping_log.py <ip> <tos>')
        sys.exit(1)

    logger = Ping_logger(ip, tos)
    print(f'==> start pinging : {ip}, tos: {tos}\n')

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
