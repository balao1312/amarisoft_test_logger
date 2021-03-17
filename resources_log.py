#!/usr/bin/python3

import datetime
import subprocess
from amari_logger import Amari_logger

# TODO when on credential , file log

class Resources_logger(Amari_logger):
    def __init__(self):
        super().__init__()
        self.log_file = self.log_folder.joinpath(
            f'log_resources_{datetime.datetime.now().date()}')
        self.send_fail_file = self.log_folder.joinpath('send_fail_resources')

    def get_cpu_usage(self):
        cmd = 'uptime'
        result = subprocess.check_output(
            [cmd], stderr=subprocess.STDOUT).decode('utf8')
        cpu_status = list(filter(None, result.split(' ')))
        cpu_load = {
            '1m': cpu_status[-3][:-1],
            '5m': cpu_status[-2][:-1],
            '15m': cpu_status[-1][:-1]
        }
        return cpu_load

    def get_mem_usage(self):
        cmd = 'free'
        result = subprocess.check_output(
            [cmd], timeout=3, stderr=subprocess.STDOUT).decode('utf8')
        line = result.split('\n')[1].split(' ')
        feilds = list(filter(None, line))
        mem_total = feilds[1]
        mem_available = feilds[6]
        mem_usage = round(((1-int(mem_available) / int(mem_total)))*100, 1)
        mem_total_G = round((int(mem_total) / 1024 / 1024), 1)
        mem_status = {
            'total': mem_total_G,
            'usage': mem_usage,
        }
        return mem_status

    def get_swap_usage(self):
        cmd = 'free'
        result = subprocess.check_output(
            [cmd], timeout=3, stderr=subprocess.STDOUT).decode('utf8')
        line = result.split('\n')[2].split(' ')
        fields = list(filter(None, line))
        swap_total = fields[1]
        swap_available = fields[3]
        swap_usage = round(((1-int(swap_available) / int(swap_total)))*100, 1)
        swap_total_G = round((int(swap_total) / 1024 / 1024), 1)
        swap_status = {
            'total': swap_total_G,
            'usage': swap_usage,
        }
        return swap_status

    def get_disk_usage(self):
        cmd = 'df -h'
        result = subprocess.check_output(
            [cmd], timeout=3, shell=True, stderr=subprocess.STDOUT).decode('utf8')
        fields = result.split('\n')[3].split(' ')
        storage_total = list(filter(None, fields))[1]
        storage_usage = list(filter(None, fields))[4]
        storage_status = {
            'total': storage_total,
            'usage': storage_usage,
        }
        return storage_status

    def get_cpu_temp(self):
        cmd = 'sensors'
        try:
            result = subprocess.check_output(
                [cmd], timeout=3, shell=True, stderr=subprocess.STDOUT).decode('utf8')
            # print(result)
            temp_status = result.split('\n')[6].split(' ')
            temp = temp_status[4][1:-2]
            return temp
        except Exception as e:
            print("==> couldn't get temp information")
            print('==> error msg: ', e)
            return 0

    def run(self):
        now_time = datetime.datetime.utcnow()
        cpu_1 = self.get_cpu_usage()['1m']
        mem_usage = self.get_mem_usage()['usage']
        mem_total = self.get_mem_usage()['total']
        storage_usage = self.get_disk_usage()['usage']
        storage_total = self.get_disk_usage()['total']
        swap_usage = self.get_swap_usage()['usage']
        swap_total = self.get_swap_usage()['total']
        cpu_temp = self.get_cpu_temp()
        output = f'''
            {now_time}
            cpu_1m: \t\t{cpu_1}
            mem_usage: \t\t{mem_usage}%
            mem_total: \t\t{mem_total}G
            storage_usage: \t{storage_usage}
            storage_total: \t{storage_total}
            swap_usage: \t{swap_usage}%
            swap_total: \t{swap_total}G
            temperature: \t{cpu_temp}'''
        print(output)

        data = {
            'measurement': 'amari_resources',
            'time': now_time,
            'fields': {
                'cpu_usage': float(cpu_1),
                'mem_usage': float(mem_usage),
                'temp': float(cpu_temp),
            }
        }
        self.send_to_influx([data])


if __name__ == '__main__':
    logger = Resources_logger()
    logger.run()
