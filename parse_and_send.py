from amari_logger import Amari_logger
from pathlib import Path
import sys

if __name__ == '__main__':
    try:
        loc = sys.argv[1]
    except:
        print('==> arg wrong, should be:\n python3 parse_and_send.py <path for file or folder>')
        sys.exit(1)

    path_object = Path(loc)

    if path_object.exists():
        parser = Amari_logger()
        parser.parse_and_send(path_object)
    else:
        print('==> target doesn\'t exists. Exited.')
