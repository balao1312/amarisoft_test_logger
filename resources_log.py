#!/usr/bin/python3

import datetime
import subprocess
from amari_logger import Amari_logger


class Resources_logger(Amari_logger):

    number_of_buffer = 1
    try:
        from config import config
        device = config['resouces_device']
    except:
        device = 'undefined'

    def __init__(self):
        super().__init__()
        self.log_file = self.log_folder.joinpath(
            f'log_resources_{datetime.datetime.now().date()}')
    
    @property
    def cpu_usage(self):
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

    @property
    def mem_usage(self):
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

    @property
    def swap_usage(self):
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

    @property
    def disk_usage(self):
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

    @property
    def cpu_temp(self):
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
                return temp if temp else 0
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
            return temp if temp else 0
        except Exception as e:
            print("==> couldn't get temp information")
            print('==> error msg: ', e)
            return 0

    def run(self):
        record_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        output = f'''
            {record_time}
            cpu_1m: \t\t{self.cpu_usage['1m']}
            mem_usage: \t\t{self.mem_usage['usage']}%
            mem_total: \t\t{self.mem_usage['total']}G
            swap_usage: \t{self.swap_usage['usage']}%
            swap_total: \t{self.swap_usage['total']}G
            storage_usage: \t{self.disk_usage['usage']}
            storage_total: \t{self.disk_usage['total']}
            temperature: \t{self.cpu_temp}
            '''
        print(output)

        data = {
            'measurement': 'resources',
            'tags': {'device': self.device},
            'time': record_time,
            'fields': {
                'cpu_usage': float(self.cpu_usage['1m']),
                'mem_usage': float(self.mem_usage['usage']),
                'temp': float(self.cpu_temp),
            }
        }
        self.logging_with_buffer(data)


if __name__ == '__main__':
    logger = Resources_logger()
    logger.run()
