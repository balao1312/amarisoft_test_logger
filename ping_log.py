#!/usr/bin/python3

import subprocess
import shlex
import sys
import os
import datetime
import time
from amari_logger import Amari_logger


class Amari_logger_ping(Amari_logger):

    def __init__(self, ip, tos):
        super().__init__()
        self.ip = ip
        self.tos = tos

        self.log_file = self.log_folder.joinpath(
            f'log_ping_{datetime.datetime.now().date()}')
        self.send_fail_file = self.log_folder.joinpath('send_fail_ping')

    def string_list_to_influx_list(self, string_list) -> list:
        influx_format_list = []
        for each in string_list:
            latency = round(float(each.split(',')[0]), 2)
            data_time = datetime.datetime.strptime(
                each.split(',')[1][:-1], '%Y-%m-%d %H:%M:%S.%f')
            tos = int(each.split(',')[2])
            data = {
                'measurement': 'ping',
                'tags': {'tos': tos},
                'time': data_time,
                'fields': {'RTT': latency}
            }
            influx_format_list.append(data)
        return influx_format_list

    def check_platform(self):
        cmd = 'uname'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8').strip()
        return result

    def run(self):
        if self.check_platform() == 'Darwin':
            tos_option_string = '-z'
        elif self.check_platform() == 'Linux':
            tos_option_string = '-Q'

        process = subprocess.Popen(shlex.split(
            f'ping {self.ip} {tos_option_string} {self.tos}'), stdout=subprocess.PIPE)

        while True:
            output = process.stdout.readline()
            if process.poll() is not None:
                break

            if output:
                line = output.strip().decode('utf8')
                data_time = datetime.datetime.utcnow()
                try:
                    latency = float(
                        list(filter(None, line.split(' ')))[6][5:10])
                    print(
                        f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, tos: {self.tos}, latency: {latency} ms')

                    self.logging(latency, data_time)
                except ValueError:
                    pass
                except IndexError:
                    pass
                except Exception as e:
                    print(f'==> error: {e.__class__} {e}')


if __name__ == '__main__':
    try:
        ip = sys.argv[1]
        tos = sys.argv[2]
    except:
        print('arg wrong, should be:\n python3 ping_log.py <ip> <tos>')
        sys.exit()

    logger = Amari_logger_ping(ip, tos)
    print(f'==> start pinging : {ip}, tos: {tos}\n')

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n\nInterrupted')
        sec_count = 9
        while logger.is_sending:
            print(
                f'==> waiting for send process to end (max {sec_count} secs) ...')
            sec_count -= 1
            time.sleep(1)
        try:
            print('\nStoped')
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f'==> error: {e.__class__} {e}')
