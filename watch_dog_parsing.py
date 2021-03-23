import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from amari_logger import Amari_logger


class MyDirEventHandler(FileSystemEventHandler):

    def on_created(self, event):
        file = Path(event.src_path)
        if file.is_dir() or file.name == '.DS_Store':
            return

        print(f'\n==> new file detected: {file}')
        parser = Amari_logger()
        parser.parse_and_send(file)
        print(f'\n==> keep watching ...')


if __name__ == "__main__":
    watching_folder_path = Path(
        input('==> Please type in the folder name to watch: '))

    if not watching_folder_path.exists():
        watching_folder_path.mkdir()

    event_handler = MyDirEventHandler()
    observer = Observer()

    observer.schedule(event_handler, watching_folder_path, recursive=True)
    observer.start()

    print('==> Start watching ...')
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
