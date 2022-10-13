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
import re


class Iperf3_logger(Amari_logger):

    def __init__(self, host, port, tos, bitrate, reverse, udp, exec_secs, buffer_length):
        super().__init__()
        self.host = host
        self.tos = tos
        self.port = port
        self.bitrate = bitrate
        self.reverse = reverse
        self.udp = udp
        self.exec_secs = exec_secs
        self.buffer_length = buffer_length

        self.record_count = 0
        self.total_mbps = 0

        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')

    def run(self):
        reverse_string = ' -R' if self.reverse else ''
        udp_string = ' -u' if self.udp else ''
        buffer_length_string = f' -l {self.buffer_length}' if self.buffer_length else ''

        average_pattern = re.compile('.*(sender|receiver)')

        cmd = f'iperf3 -c {self.host} -p {self.port} -S {self.tos} -b {self.bitrate} -t {self.exec_secs}{buffer_length_string}{reverse_string}{udp_string} -f m --forceflush'
        print(f'==> cmd send: \n\n\t{cmd}\n')

        process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)

        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                print()
                self.clean_buffer_and_send()
                break

            if output:
                line = output.strip().decode('utf8')
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    self.record_count += 1
                    self.total_mbps += mbps

                    if average_pattern.match(line):
                        print('-' * 80)
                        print(average_pattern.search(line).group(0))
                        continue

                    print(
                        f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, dst:{self.host}, tos:{self.tos}, bitrate: {mbps} Mbit/s')

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
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--host', required=True,
                        type=str, help='iperf server ip')
    parser.add_argument('-p', '--port', default=5201,
                        type=int, help='iperf server port')
    parser.add_argument('-S', '--tos', default=0, type=int,
                        help='type of service value')
    parser.add_argument('-b', '--bitrate', default=0,
                        type=str, help='the limit of bitrate(M/K)')
    parser.add_argument('-t', '--exec_secs', default=0, type=int,
                        help='time duration (secs)')
    parser.add_argument('-l', '--buffer_length', default=128, type=int,
                        help='length of buffer to read or write (default 128 KB for TCP, 8KB for UDP)')

    parser.add_argument('-u', '--udp', action="store_true",
                        help='use udp instead of tcp.')
    parser.add_argument('-R', '--reverse', action="store_true",
                        help='reverse to downlink from server')
    args = parser.parse_args()

    logger = Iperf3_logger(host=args.host, port=args.port, tos=args.tos,
                           bitrate=args.bitrate, reverse=args.reverse, udp=args.udp, exec_secs=args.exec_secs, buffer_length=args.buffer_length)

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
