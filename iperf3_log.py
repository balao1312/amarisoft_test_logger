#!/usr/bin/python3

import subprocess
import shlex
import sys
import os
import datetime
import time
from amari_logger import Amari_logger


class Amari_logger_iperf3(Amari_logger):
    def __init__(self, ip, port, tos, bitrate, reverse):
        super().__init__()
        self.ip = ip
        self.tos = tos
        self.port = port
        self.bitrate = bitrate
        self.reverse = reverse

        self.log_file = self.log_folder.joinpath(
            f'log_iperf3_{datetime.datetime.now().date()}')
        self.send_fail_file = self.log_folder.joinpath('send_fail_iperf3')

    def string_list_to_influx_list(self, string_list) -> list:
        influx_format_list = []
        for each in string_list:
            mbps = round(float(each.split(',')[0]), 4)
            data_time = datetime.datetime.strptime(
                each.split(',')[1][:-1], '%Y-%m-%d %H:%M:%S.%f')
            tos = int(each.split(',')[2])

            data = {
                'measurement': 'iperf3',
                'tags': {'tos': tos},
                'time': data_time,
                'fields': {'Mbps': mbps}
            }
            influx_format_list.append(data)
        return influx_format_list

    def run(self):
        reverse_string = '-R' if self.reverse == True else ''
        process = subprocess.Popen(shlex.split(
            f'iperf3 -p {self.port} --forceflush -c {self.ip} -t 0 -l 999 -f m -S {self.tos} -b {self.bitrate}M {reverse_string}'), stdout=subprocess.PIPE)

        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break

            if output:
                line = output.strip().decode('utf8')
                data_time = datetime.datetime.utcnow()
                try:
                    mbps = float(list(filter(None, line.split(' ')))[6])
                    print(
                        f'{mbps} Mbit/s, tos:{self.tos}, {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

                    self.logging(mbps, data_time)
                except ValueError:
                    pass
                except IndexError:
                    pass
                except Exception as e:
                    print(f'==> error: {e}')


if __name__ == '__main__':
    try:
        ip = sys.argv[1]
        port = sys.argv[2]
        tos = sys.argv[3]
        bitrate = sys.argv[4]
        reverse = True if sys.argv[5] == '1' else False
    except:
        print('arg wrong, should be:\n python3 iperf3_log.py <ip> <port> <tos> <bitrate(M)> <Reverse?1:0>')
        sys.exit()

    logger = Amari_logger_iperf3(ip, port, tos, bitrate, reverse)

    print(
        f'==> start iperf3ing : {ip}:{port}, tos:{tos}, bitrate:{bitrate}M, reverse:{reverse}\n')

    try:
        logger.run()
    except KeyboardInterrupt:
        count = 9
        while logger.sending:
            print(
                f'==> waiting for send process to end (max {count} secs) ...')
            count -= 1
            time.sleep(1)
        try:
            print('\nStoped')
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f'==> error: {e}')
