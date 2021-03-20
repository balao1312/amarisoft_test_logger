import pathlib
import threading
import pickle
import json
from influxdb import InfluxDBClient
from config import config


class Amari_logger:

    db_timeout = config['db_connect_timeout']
    db_retries = config['db_connect_retries']
    number_of_buffer = config['number_of_buffer']
    
    data_pool = []
    is_sending = False
    is_send_to_db = True

    log_folder = pathlib.Path.cwd().joinpath('logs')

    try:
        from credential import db_config
        influxdb_ip = db_config['influxdb_ip']
        influxdb_port = db_config['influxdb_port']
        influxdb_username = db_config['influxdb_username']
        influxdb_password = db_config['influxdb_password']
        influxdb_dbname = db_config['influxdb_dbname']
    except ModuleNotFoundError:
        print('\n==> credential.py is not found, send to db function is disabled.')
        is_send_to_db = False
    except (NameError, ImportError, KeyError) as e:
        print('\n==> db_config format incorrect, send to db function is disabled.')
        is_send_to_db = False

    def __init__(self):
        if not self.log_folder.exists():
            self.log_folder.mkdir()
        if self.is_send_to_db:
            print(f'\n==> database used in influxdb: {self.influxdb_dbname}')

    def write_to_file(self):
        with open(self.log_file, 'a') as f:
            for each in self.data_pool:
                f.write(f'{json.dumps(each)}\n')
        print(f'==> data written to log file: {self.log_file}. ')

    def send_to_influx(self, influx_format_list):
        try:
            db_cli = InfluxDBClient(
                self.influxdb_ip,
                self.influxdb_port,
                self.influxdb_username,
                self.influxdb_password,
                self.influxdb_dbname,
                timeout=self.db_timeout,
                retries=self.db_retries)
        except Exception as e:
            print(f'==> error: {e.__class__} {e}')

        # add up those unsend_data if exists
        if self.send_fail_file.exists():
            with open(self.send_fail_file, 'rb') as f:
                unsend_data = pickle.load(f)
            influx_format_list += unsend_data

            self.send_fail_file.unlink()

        try:
            print('==> trying sending to db ...')
            self.is_sending = True
            db_cli.write_points(influx_format_list)
            print('==> data sent.')
            self.is_sending = False

        except Exception as e:
            print('==> send failed.')
            print(f'==> error: {e.__class__} {e}')

            # check if there is new unsend_data generate by other thread
            if self.send_fail_file.exists():
                with open(self.send_fail_file, 'rb') as f:
                    prev_data = pickle.load(f)
                influx_format_list += prev_data

            with open(self.send_fail_file, 'wb') as f:
                pickle.dump(influx_format_list, f)
            self.is_sending = False

    def logging_with_buffer(self, data):
        self.data_pool.append(data)
        if len(self.data_pool) >= self.number_of_buffer:
            self.write_to_file()

            if self.is_send_to_db == True:
                thread_1 = threading.Thread(
                    target=self.send_to_influx, args=(self.data_pool,))
                thread_1.start()

            self.data_pool = []
    
    def clear_buffer(self):
        if self.data_pool:
            self.write_to_file()
            if self.is_send_to_db == True:
                thread_2 = threading.Thread(
                    target=self.send_to_influx, args=(self.data_pool,))
                thread_2.start()
