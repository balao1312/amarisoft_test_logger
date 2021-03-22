from amari_logger import Amari_logger
from pathlib import Path
import sys

class Parse_and_Send(Amari_logger):

    def __init__(self):
        super().__init__()


if __name__ == '__main__':
    try:
        loc = sys.argv[1]
    except:
        print('==> arg wrong, should be:\n python3 parse_and_send.py <path for file or folder>')
        sys.exit()

    f_object = Path(loc)

    if f_object.exists():
        parser = Parse_and_Send()
        parser.parse_and_send(f_object)
    else:
        print('==> target doesn\'t exists. Exited.')
