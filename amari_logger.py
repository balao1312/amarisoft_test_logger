import pathlib
import threading
import pickle
from influxdb import InfluxDBClient
from credential import db_config


class Amari_logger:
    data_pool = []
    number_of_buffer = 60
    sending = False

    influxdb_ip = db_config['influxdb_ip']
    influxdb_port = db_config['influxdb_port']
    influxdb_username = db_config['influxdb_username']
    influxdb_password = db_config['influxdb_password']
    influxdb_dbname = db_config['influxdb_dbname']

    log_folder = pathlib.Path.cwd().joinpath('logs')

    def __init__(self):
        if not self.log_folder.exists():
            self.log_folder.mkdir()
        print(f'\n==> database used in influxdb: {self.influxdb_dbname}')

    def logging(self, data, data_time):
        self.data_pool.append(f'{data},{data_time},{self.tos}\n')
        if len(self.data_pool) >= self.number_of_buffer:
            with open(self.log_file, 'a') as f:
                for each in self.data_pool:
                    f.write(each)

            thread_1 = threading.Thread(
                target=self.send_to_influx, args=(self.string_list_to_influx_list(self.data_pool),))
            thread_1.start()

            self.data_pool = []

    def send_to_influx(self, influx_format_list):
        db_cli = InfluxDBClient(
            self.influxdb_ip,
            self.influxdb_port,
            self.influxdb_username,
            self.influxdb_password,
            self.influxdb_dbname,
            timeout=5,
            retries=2)

        # add up those unsend_data if exists
        if self.send_fail_file.exists():
            with open(self.send_fail_file, 'rb') as f:
                unsend_data = pickle.load(f)
            influx_format_list += unsend_data

            self.send_fail_file.unlink()

        try:
            print('==> check and try to send ...')
            self.sending = True
            db_cli.write_points(influx_format_list)
            print('==> data sent.')
            self.sending = False

        except Exception as e:
            print('==> send failed.')
            print('==> error msg:', e)

            # check if there is new unsend_data generate by other thread
            if self.send_fail_file.exists():
                with open(self.send_fail_file, 'rb') as f:
                    prev_data = pickle.load(f)
                influx_format_list += prev_data

            with open(self.send_fail_file, 'wb') as f:
                pickle.dump(influx_format_list, f)
            self.sending = False
