#!/usr/bin/python3

import datetime
import subprocess
from amari_logger import Amari_logger


class Resources_logger(Amari_logger):


    def __init__(self):
        try:
            from config import config
            self.server_name = config['server_name']
        except:
            self.server_name = 'undefined'

        super().__init__()

        self.number_of_buffer = 1
        self.cpu_load_warning_cap = 4.0
        self.mem_usage_warning_cap = 80.0     # percentage
        self.log_file = self.log_folder.joinpath(
            f'log_resources_{datetime.datetime.now().date()}')

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

        if swap_total == '0':
            swap_status = {
                'total': 0,
                'usage': 0,
            }

            return swap_status

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
        cmd = 'cat /etc/os-release'
        result = subprocess.check_output(
            [cmd], timeout=3, shell=True, stderr=subprocess.STDOUT).decode('utf8')
        if result.split('\n')[1] == 'NAME="Raspbian GNU/Linux"':
            cmd = 'vcgencmd measure_temp'
            try:
                result = subprocess.check_output(
                    [cmd], timeout=3, shell=True, stderr=subprocess.STDOUT).decode('utf8')
                # print(result)
                temp = result[5:9]
                return temp
            except Exception as e:
                print("==> couldn't get temp information")
                print('==> error msg: ', e)
                return 0

        cmd = 'sensors'
        try:
            result = subprocess.check_output(
                [cmd], timeout=3, shell=True, stderr=subprocess.STDOUT).decode('utf8')
            # print(result)
            temp = result.split('\n')[2][16:20]
            return temp
        except Exception as e:
            print("==> couldn't get temp information")
            print('==> error msg: ', e)
            return 0

    def run(self):
        record_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cpu_1m = self.get_cpu_usage()['1m']
        mem_usage = self.get_mem_usage()['usage']
        mem_total = self.get_mem_usage()['total']
        swap_usage = self.get_swap_usage()['usage']
        swap_total = self.get_swap_usage()['total']
        storage_usage = self.get_disk_usage()['usage']
        storage_total = self.get_disk_usage()['total']
        temperature = self.get_cpu_temp()
        output = f'''
            {record_time}
            cpu_1m: \t\t{cpu_1m}
            mem_usage: \t\t{mem_usage} %
            mem_total: \t\t{mem_total} G
            swap_usage: \t{swap_usage} %
            swap_total: \t{swap_total} G
            storage_usage: \t{storage_usage} %
            storage_total: \t{storage_total} G
            temperature: \t{temperature} c
            '''
        print(output)
        print(f'==> server name to tag in db: {self.server_name}')

        data = {
            'measurement': 'amari_resources',
            'tags': {'device': self.server_name},
            'time': record_time,
            'fields': {
                'cpu_usage': float(cpu_1m),
                'mem_usage': float(mem_usage),
                'temp': float(temperature),
            }
        }
        self.logging_with_buffer(data)

        if float(cpu_1m) > self.cpu_load_warning_cap:
            msg = f'\n{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nCPU load 1m of {self.server_name} is greater than {self.cpu_load_warning_cap}.'
            self.send_line_notify('balao', msg)

        if float(mem_usage) > self.mem_usage_warning_cap:
            msg = f'\n{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nMemory usage of {self.server_name} is greater than {self.mem_usage_warning_cap} %.'
            self.send_line_notify('balao', msg)


if __name__ == '__main__':
    logger = Resources_logger()
    logger.run()

