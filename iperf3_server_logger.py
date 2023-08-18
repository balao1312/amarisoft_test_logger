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

    def __init__(self, port, parallel, notify, label):
        super().__init__()
        self.port = port
        self.detect_parallel = parallel
        self.notify_when_terminated = notify
        self.label = label

        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')

    def run(self):

        cmd = f'iperf3 -s -p {self.port} -f m'

        print(f'==> cmd send: \n\n\t{cmd}\n')
        print(f'==> parallel mode: {self.detect_parallel}')
        print(f'==> notify when terminated: {self.notify_when_terminated}')
        sleep(1)

        average_pattern = re.compile(r'.*(sender|receiver)')
        sum_parallel_pattern = re.compile(r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')
        standby_pattern = re.compile(r'Server listening')

        # iperf3: the client has terminated
        terminated_pattern = re.compile(r'iperf3:')

        child = pexpect.spawnu(cmd, timeout=10)

        counter = 0
        while True:
            try:
                child.expect('\n')
                line = child.before
                print(line)
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # detect session end and clean buffer
                if standby_pattern.match(line):
                    self.clean_buffer_and_send()

                # notify when terminated
                if terminated_pattern.match(line) and self.notify_when_terminated:
                    msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{self.label}\n{line}.'
                    thread_1 = threading.Thread(
                        target=self.send_line_notify, args=('balao', msg))
                    thread_1.start()

                # check if in parallel mode
                if not self.detect_parallel:
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

                # print(
                #     f'{counter}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, bitrate: {mbps} Mbit/s')

                data = {
                    'measurement': 'iperf3',
                    'tags': {'label': self.label},
                    'time': record_time,
                    'fields': {'Mbps': mbps}
                }

                self.logging_with_buffer(data)

            except pexpect.TIMEOUT as e:
                # print('==> timeout.')
                pass
            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{self.lable} iperf server got an EOF.'
                thread_1 = threading.Thread(
                    target=self.send_line_notify, args=('balao', msg))
                thread_1.start()
                break
            except (ValueError, IndexError):
                pass
            # except Exception as e:
            #     print(f'==> error: {e.__class__} {e}')

        self.clean_buffer_and_send()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', metavar='', default=5201, type=int,
                        help='iperf server port')
    parser.add_argument('-P', '--parallel', action="store_true",
                        help='detect client in parallel mode')
    parser.add_argument('-n', '--notify', action="store_true",
                        help='notify when terminated')
    parser.add_argument('-l', '--label', metavar='', default='', type=str, required=True,
                        help='data label')

    args = parser.parse_args()

    logger = Iperf3_logger(
        port=args.port,
        parallel=args.parallel,
        notify=args.notify,
        label=args.label
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

