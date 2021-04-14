#!/usr/bin/python3

import sys
import os
from time import sleep
from datetime import datetime
from copy import copy
from amari_logger import Amari_logger
import pexpect


class Con_stats_logger(Amari_logger):

    def __init__(self):
        super().__init__()

        self.log_file = self.log_folder.joinpath(
            f'log_con_stats_{datetime.now().date()}')

    def run(self):
        c = pexpect.spawnu('screen -x')
        # target = re.compile('.*time=(\d*.\d*).*')
        c.sendcontrol('a')
        c.sendline('1')
        c.sendline('t')

        def get_column(x):
            if x != ' ' and x != '':
                return True
            else:
                return False

        while 1:
            c.expect('\n')
            realtime_output = c.before
            columns = list(filter(get_column, realtime_output.split(' ')))

            if len(columns) != 20:
                continue
            if columns[0] == 'UE_ID':
                continue

            record_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            stats_data = {
                'UE_ID': columns[0],
                'CL': columns[1],
                'RNTI': columns[2],
                'DL': {
                    'C': columns[3],
                    'cqi': columns[4],
                    'ri': columns[5],
                    'mcs': columns[6],
                    'retx': columns[7],
                    'txok': columns[8],
                    'brate': columns[9],
                },
                'UL': {
                    'snr': columns[10],
                    'puc1': columns[11],
                    'mcs': columns[12],
                    'rxko': columns[13],
                    'rxok': columns[14],
                    'brate': columns[15],
                    '#its': columns[16],
                    'phr': columns[17],
                    'pl': columns[18],
                    'ta': columns[19][:-1],
                }
            }
            
            try:
                dl_mcs = float(stats_data['DL']['mcs'])
                ul_mcs = float(stats_data['UL']['mcs'])
                ue_id = int(stats_data['UE_ID'])
            except ValueError:
                continue

            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, dl_mcs: {dl_mcs}, ul_mcs: {ul_mcs}")

            data = {
                'measurement': 'con_stats',
                'tags': {'UE_ID': ue_id},
                'time': record_time,
                'fields': {
                    'dl_mcs': dl_mcs,
                    'ul_mcs': ul_mcs,
                }
            }

            self.logging_with_buffer(data)


if __name__ == '__main__':
    logger = Con_stats_logger()

    print(
        f'==> start collecting Amarisoft connection stats ...')

    try:
        logger.run()
    except KeyboardInterrupt:
        print('\n==> Interrupted.\n')
        logger.clean_buffer()
        sleep(0.1)  # for avoiding the bug I cannot figure out
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
