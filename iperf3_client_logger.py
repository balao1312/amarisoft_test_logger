#!/usr/bin/python3

from pathlib import Path
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

    def __init__(self, host, port, tos, bitrate, reverse, udp, duration, buffer_length, window, parallel, set_mss, label, project_field_name):
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
        self.label = label
        self.project_field_name = project_field_name

        # define RE patterns
        self.average_pattern = re.compile(r'.*(sender|receiver)')
        self.sum_parallel_pattern = re.compile(
            r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')

        self.display_all_option()

    def display_all_option(self):
        print('-' * 140)
        print(self.turn_to_form('target ip', self.host))
        print(self.turn_to_form('execute times(secs)', self.duration))
        print(self.turn_to_form('port', self.port))
        print(self.turn_to_form('TOS, type of service value', self.tos))
        print(self.turn_to_form('bitrate', self.bitrate))
        print(self.turn_to_form('reverse', str(bool(self.reverse))))
        print(self.turn_to_form('UDP', str(bool(self.udp))))
        print(self.turn_to_form('buffer_lenth', self.buffer_length))
        print(self.turn_to_form('window', self.window))
        print(self.turn_to_form('Parallel', self.parallel))
        print(self.turn_to_form('set_mss', self.set_mss))
        # TODO feat:notify
        # print(self.turn_to_form('send nofify', str(bool(self.will_send_notify))))
        print(self.turn_to_form('send data to db', str(bool(self.is_send_to_db))))
        print(self.turn_to_form('data label in db', self.label))
        print(self.turn_to_form('project field name', self.project_field_name))

    def turn_to_form(self, a, b):
        return f'| {a:<50}| {b:<85}|\n{"-" * 140}'

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_iperf3_client_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')

        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

        print(
            f'==> iperf3 stdout will be logged to: {self.stdout_log_file}.txt')

    def parse_args_to_string(self):
        self.tos_string = f' -S {self.tos}' if self.tos else ''
        self.bitrate_string = f' -b {self.bitrate}' if self.bitrate else ''
        self.buffer_length_string = f' -l {self.buffer_length}' if self.buffer_length else ''
        self.window_string = f' -w {self.window}' if self.window else ''
        self.parallel_string = f' -P {self.parallel}' if self.parallel else ''
        self.set_mss_string = f' -M {self.set_mss}' if self.set_mss else ''

        self.reverse_string = ' -R' if self.reverse else ''
        self.udp_string = ' -u' if self.udp else ''

        self.cmd = f'iperf3 -c {self.host} -p {self.port} -t {self.duration} -f m'\
            f'{self.tos_string}'\
            f'{self.bitrate_string}'\
            f'{self.buffer_length_string}'\
            f'{self.window_string}'\
            f'{self.parallel_string}'\
            f'{self.set_mss_string}'\
            f'{self.reverse_string}'\
            f'{self.udp_string}'
        print(f'==> cmd send: \n\n\t{self.cmd}\n')
        self.stdout_log_object.write(f'iperf3 cmd: {self.cmd}\n{"-"*80}\n')

    def show_progress(self, counter, mbps):
        print(
            f'{counter}: '
            f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, '
            f'dst: {self.host}, '
            # f'tos: {self.tos}, '
            f'label: {self.label}, '
            f'bitrate: {mbps} Mbit/s'
        )

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
                'tos': self.tos,
                'label': self.label
            },
            'time': record_time,
            'fields': {'Mbps': mbps}
        }

    def run(self):
        if input('Please confirm info above and press enter to continue.\n') != '':
            return
        self.refresh_log_file()
        self.parse_args_to_string()

        child = pexpect.spawnu(self.cmd, timeout=10,
                               logfile=self.stdout_log_object)

        zero_counter = 0
        counter = 0
        while True:
            try:
                child.expect('\n')
                line = child.before
                record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # check if parallel number > 2
                # must be a better way, TODO
                if self.parallel < 2:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    counter += 1
                else:
                    if not self.sum_parallel_pattern.search(line):
                        continue
                    else:
                        mbps = float(
                            self.sum_parallel_pattern.search(line).group(1))
                        counter += 1

                if self.check_if_is_summary_and_show(line):
                    continue

                self.show_progress(counter, mbps)

                data = self.gen_influx_format(record_time, mbps)
                self.logging_with_buffer(data)

                if mbps == 0:
                    zero_counter += 1
                    if zero_counter == 180:
                        print('Can\'t get result after 60 secs, stopped.')
                        break
                else: 
                    zero_counter = 0

            except pexpect.exceptions.EOF as e:
                print('==> got EOF, ended.')
                self.stdout_log_object.close()
                break
            except (ValueError, IndexError):
                # skip iperf stdout that DONT contain throughput lines
                pass
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
    parser.add_argument('-L', '--label', metavar='', default='none', type=str,
                        help='data label')
    parser.add_argument('-F', '--project_field_name', metavar='', default="", type=str,
                        help='Name of the project field')

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
        set_mss=args.set_mss,
        label=args.label,
        project_field_name=args.project_field_name
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
