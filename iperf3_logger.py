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


class Iperf3_logger(Amari_logger):

    def __init__(self, host, port, tos, bitrate, reverse, udp, duration, buffer_length, window, parallel, set_mss):
        super().__init__()
        self.host = host
        self.tos = tos
        self.port = port
        self.bitrate = bitrate
        self.reverse = reverse
        self.udp = udp
        self.duration = duration
        self.buffer_length = buffer_length
        self.window = window
        self.parallel = parallel
        self.set_mss = set_mss

        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')

    def run(self):
        # parse options to cmd string
        tos_string = f' -S {self.tos}' if self.tos else ''
        bitrate_string = f' -b {self.bitrate}' if self.bitrate else ''
        buffer_length_string = f' -l {self.buffer_length}' if self.buffer_length else ''
        window_string = f' -w {self.window}' if self.window else ''
        parallel_string = f' -P {self.parallel}' if self.parallel else ''
        set_mss_string = f' -M {self.set_mss}' if self.set_mss else ''

        reverse_string = ' -R' if self.reverse else ''
        udp_string = ' -u' if self.udp else ''

        cmd = f'iperf3 -c {self.host} -p {self.port} -t {self.duration} -f m'\
            f'{tos_string}'\
            f'{bitrate_string}'\
            f'{buffer_length_string}'\
            f'{window_string}'\
            f'{parallel_string}'\
            f'{set_mss_string}'\
            f'{reverse_string}'\
            f'{udp_string}'

        print(f'==> cmd send: \n\n\t{cmd}\n')
        sleep(1)

        average_pattern = re.compile(r'.*(sender|receiver)')
        sum_parallel_pattern = re.compile(r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')

        child = pexpect.spawnu(cmd, timeout=10)

        counter = 0

        while True:
            try:
                child.expect('\n')
                line = child.before
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # check if parallel number > 2
                if self.parallel < 2:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    counter += 1
                else:
                    if not sum_parallel_pattern.search(line):
                        continue
                    else:
                        mbps = float(
                            sum_parallel_pattern.search(line).group(1))
                        counter += 1
                        # print(mbps)

                # show summary
                if average_pattern.match(line):
                    print(average_pattern.search(line).group(0))
                    continue

                print(
                    f'{counter}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, dst:{self.host}, tos:{self.tos}, bitrate: {mbps} Mbit/s')

                data = {
                    'measurement': 'iperf3',
                    'tags': {'tos': self.tos},
                    'time': record_time,
                    'fields': {'Mbps': mbps}
                }

                self.logging_with_buffer(data)

            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                break
            except (ValueError, IndexError):
                pass
            # except Exception as e:
            #     print(f'==> error: {e.__class__} {e}')

        self.clean_buffer_and_send()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--host', metavar='', required=True, type=str,
                        help='iperf server ip')
    parser.add_argument('-p', '--port', metavar='', default=5201, type=int,
                        help='iperf server port')
    parser.add_argument('-S', '--tos', metavar='', default=0, type=int,
                        help='type of service value')
    parser.add_argument('-b', '--bitrate', metavar='', default=0, type=str,
                        help='the limit of bitrate(M/K)')
    parser.add_argument('-t', '--duration', metavar='', default=0, type=int,
                        help='time duration (secs)')
    parser.add_argument('-l', '--buffer_length', metavar='', default=0, type=int,
                        help='length of buffer to read or write (default 128 KB for TCP, 8KB for UDP)')
    parser.add_argument('-w', '--window', metavar='', default=0, type=str,
                        help='set send/receive socket buffer sizes.(indirectly sets TCP window size)')
    parser.add_argument('-P', '--parallel', metavar='', default=0, type=int,
                        help='number of parallel client streams to run')
    parser.add_argument('-M', '--set-mss', metavar='', default=0, type=int,
                        help='set TCP/SCTP maximum segment size (MTU - 40 bytes)')

    parser.add_argument('-u', '--udp', action="store_true",
                        help='use udp instead of tcp.')
    parser.add_argument('-R', '--reverse', action="store_true",
                        help='reverse to downlink from server')
    args = parser.parse_args()

    logger = Iperf3_logger(
        host=args.host,
        port=args.port,
        tos=args.tos,
        bitrate=args.bitrate,
        reverse=args.reverse,
        udp=args.udp,
        duration=args.duration,
        buffer_length=args.buffer_length,
        window=args.window,
        parallel=args.parallel,
        set_mss= args.set_mss
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
    # except Exception as e:
    #     print(f'==> error: {e.__class__} {e}')
