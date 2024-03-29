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
import subprocess
import shlex
import signal
import threading


class Iperf3_logger(Amari_logger):

    def __init__(self, host, port, tos, bitrate, reverse, udp, duration, buffer_length, window, parallel, set_mss, label, project_field_name, is_try_restart, dont_send_to_db, is_notify_when_disconnect, notify_dst):
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
        self.is_try_restart = is_try_restart
        self.dont_send_to_db = dont_send_to_db
        self.is_notify_when_disconnect = is_notify_when_disconnect
        self.notify_dst = notify_dst

        # define RE patterns
        self.average_pattern = re.compile(r'.*(sender|receiver)')
        self.single_thread_mode_throughput_pattern = re.compile(
            r'.*\ ([0-9.]*)\ Mbits\/sec')
        self.multi_threads_mode_throughput_pattern = re.compile(
            r'^\[SUM\].*\ ([0-9.]*)\ Mbits\/sec')

        self.parse_args_to_string()
        self.display_all_option()
        self.validate_notify_dst()

        # start notify check on background after child process is established if notify function is on
        if self.is_notify_when_disconnect:
            self.thread_check_unsend_line_notify = threading.Thread(
                target=self.check_unsend_line_notify_and_try_send, args=([]))
            self.thread_check_unsend_line_notify.start()

    def display_all_option(self):
        print('\n==> Tool related args:')
        print('-' * 120)
        # TODO feat:notify
        # print(self.turn_to_form('send nofify', str(bool(self.will_send_notify))))
        print(self.turn_to_form('influxdb database', self.influxdb_dbname))
        print(self.turn_to_form('send data to db',
              str(bool(not self.dont_send_to_db))))
        print(self.turn_to_form('data label in db', self.label))
        print(self.turn_to_form('project field name', self.project_field_name))
        print(self.turn_to_form('try restart', str(bool(self.is_try_restart))))
        print(self.turn_to_form('notify when disconnect', str(bool(self.is_notify_when_disconnect))))
        print(self.turn_to_form('notify destination', self.notify_dst))
        print(f'==> original cmd send: \n\n\t{self.cmd}\n')

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

    def turn_to_form(self, a, b):
        return f'| {a:<30}| {b:<85}|\n{"-" * 120}'

    def refresh_log_file(self):
        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.now().date()}')
        self.stdout_log_file = self.log_folder.joinpath(
            f'stdout_iperf3_client_{datetime.now().date()}.txt')
        self.stdout_log_object = open(self.stdout_log_file, 'a')

        self.stdout_log_object.write(
            f'\n\n{"-"*80}\nNew session starts at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"-"*80}\n')

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

    def show_progress(self, seq_counter, mbps):
        print(
            f'{seq_counter}: '
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

    def gen_notify_format(self, msg):
        return {
            'project_field_name': self.project_field_name,
            'dst': self.notify_dst,
            'msg': msg
        }

    @property
    def platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result

    def wait_until_connection_is_back(self):
        sleep(2)
        print(
            f'\n==> Trying to check iperf3 server to know whether connection is back or not...')

        # make sure iperf server is back
        if self.platform == 'Darwin':
            cmd = f'nc -vz -w 2 {self.host} {self.port}'
        elif self.platform == 'Linux':
            cmd = f'nc -vz -w 2 {self.host} {self.port}'

        while True:
            result = subprocess.run(shlex.split(
                cmd), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            if result.returncode:
                print('.', end='')
                sleep(1)
            else:
                print(f'\n==> Connection is back. Try restart iperf session...\n')
                break
        return

    def validate_to_send_notify(self, msg):
        if self.can_send_line_notify:
            self.unsend_line_notify_queue.put(self.gen_notify_format(msg))

    def send_to_db_on_demend(self, record_time, mbps):
        if not self.dont_send_to_db:
            data = self.gen_influx_format(record_time, mbps)
            self.logging_with_buffer(data)
        return

    def check_if_is_disconnected(self, mbps):
        if mbps == 0:
            self.zero_counter += 1
            if self.zero_counter >= 180:
                print('\n==> Can\'t get result from server for 3 mins, session stopped.(Disconnecion may be the reason)\n')
                notify_msg = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\niperf3 client is unable to reach iperf3 server.'
                if self.is_notify_when_disconnect:
                    self.validate_to_send_notify(notify_msg)
                return True
        else:
            self.zero_counter = 0
            return False

    def run_iperf3_session(self):
        print('==> Start iperf3 session...\n')
        self.refresh_log_file()
        sleep(1)

        child = pexpect.spawnu(self.cmd, timeout=10,
                               logfile=self.stdout_log_object)
        self.zero_counter = 0
        seq_counter = 0
        while True:
            try:
                child.expect('\n')
            except pexpect.exceptions.EOF as e:
                print(
                    '==> Got an EOF, ended. Cause: iperf server not ready or normal timeup end.')
                break
            line = child.before
            record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # get throughput but check first if parallel number > 2
            if self.parallel < 2:
                if not self.single_thread_mode_throughput_pattern.search(line):
                    continue
                mbps = float(
                    self.single_thread_mode_throughput_pattern.search(line).group(1))
                seq_counter += 1
            else:
                if not self.multi_threads_mode_throughput_pattern.search(line):
                    continue
                else:
                    mbps = float(
                        self.multi_threads_mode_throughput_pattern.search(line).group(1))
                    seq_counter += 1

            if self.check_if_is_summary_and_show(line):
                continue

            self.show_progress(seq_counter, mbps)
            self.send_to_db_on_demend(record_time, mbps)

            if self.check_if_is_disconnected(mbps):
                break

        self.stdout_log_object.close()
        self.clean_buffer_and_send()
        child.kill(signal.SIGINT)
        self.number_of_instances -= 1
        return

    def run(self):
        if input('Please confirm info above and press enter to continue.\n') != '':
            return
        self.run_iperf3_session()

        if self.is_try_restart and self.duration == 0:
            while True:
                self.wait_until_connection_is_back()
                self.run_iperf3_session()
                sleep(3)


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
    parser.add_argument('-T', '--is_try_restart', action="store_true",
                        help='try to restart iperf session when server is available')
    parser.add_argument('-U', '--dont_send_to_db', action="store_true",
                        help='disable sending record to db')
    parser.add_argument('-n', '--is_notify_when_disconnect', action="store_true",
                        help='notify when terminated')
    parser.add_argument('-D', '--notify_dst', metavar='', default='', type=str,
                        help='line notify send destination')

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
        project_field_name=args.project_field_name,
        is_try_restart=args.is_try_restart,
        dont_send_to_db=args.dont_send_to_db,
        is_notify_when_disconnect=args.is_notify_when_disconnect,
        notify_dst=args.notify_dst
    )

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer_and_send()
        sleep(0.1)
        max_sec_count = logger.db_retries * logger.db_timeout
        countdown = copy(max_sec_count)
        while logger.is_in_sending_to_db_session:
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
