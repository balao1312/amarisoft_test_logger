#!/usr/bin/python3

import subprocess
import shlex
import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger


class Iperf3_logger(Amari_logger):

    def __init__(self, ip, port, tos, bitrate, reverse):
        super().__init__()
        self.ip = ip
        self.tos = tos
        self.port = port
        self.bitrate = bitrate
        self.reverse = reverse
        self.record_count = 0
        self.total_mbps = 0

        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')

    def run(self):
        reverse_string = '-R' if self.reverse == True else ''
        process = subprocess.Popen(shlex.split(
            f'iperf3 -p {self.port} --forceflush -c {self.ip} -t 0 -l 999 -f m -S {self.tos} -b {self.bitrate}M {reverse_string} -u'), stdout=subprocess.PIPE)

        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break

            if output:
                self.record_count += 1
                line = output.strip().decode('utf8')
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    self.total_mbps += mbps
                    print(
                        f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, tos:{self.tos}, bitrate: {mbps} Mbit/s')

                    data = {
                        'measurement': 'iperf3',
                        'tags': {'tos': self.tos},
                        'time': record_time,
                        'fields': {'Mbps': mbps}
                    }

                    self.logging_with_buffer(data)

                except (ValueError, IndexError):
                    pass
                except Exception as e:
                    print(f'==> error: {e.__class__} {e}')


if __name__ == '__main__':
    try:
        ip = sys.argv[1]
        port = sys.argv[2]
        tos = sys.argv[3]
        bitrate = sys.argv[4]
        reverse = True if sys.argv[5] == '1' else False
    except:
        print('==> arg wrong, should be:\n python3 iperf3_log.py <ip> <port> <tos> <bitrate(M)> <Reverse?1:0>')
        sys.exit(1)

    logger = Iperf3_logger(ip, port, tos, bitrate, reverse)

    print(
        f'==> start iperf3ing : {ip}:{port}, tos:{tos}, bitrate:{bitrate}M, reverse:{reverse}\n')

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer()
        sleep(0.1)  # for avoiding the bug I cannot figure out
        max_sec_count = logger.db_retries * logger.db_timeout
        countdown = copy(max_sec_count)
        print(f'Average: {logger.total_mbps / logger.record_count} Mbit/s')
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
