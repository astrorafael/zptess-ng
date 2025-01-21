import os

from argparse import ArgumentParser
from lica.validators import vdir

def idir() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-i",
        "----input-dir",
        type=vdir,
        default=os.getcwd(),
        metavar="<Dir>",
        help="Input CSV directory (default %(default)s)",
    )
    return parser

def odir() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-o",
        "----output-dir",
        type=vdir,
        default=os.getcwd(),
        metavar="<Dir>",
        help="Output CSV directory (default %(default)s)",
    )
    return parser