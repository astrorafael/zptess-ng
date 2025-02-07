# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import os

from argparse import ArgumentParser

# ---------------------------
# Third-party library imports
# ----------------------------

from lica.validators import vdir
from lica.asyncio.photometer import Model as PhotModel, Sensor

# --------------
# local imports
# -------------

from .validator import vendpoint
from ...lib import CentralTendency


def idir() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-i",
        "--input-dir",
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
        "--output-dir",
        type=vdir,
        default=os.getcwd(),
        metavar="<Dir>",
        help="Output CSV directory (default %(default)s)",
    )
    return parser


def buf() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-b",
        "--buffer",
        type=int,
        default=None,
        help="Circular buffer size (default %(default)s)",
    )
    return parser


def dry() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-d",
        "--dry-run",
        default=False,
        action="store_true",
        help="Query photometer info and exit (default %(default)s)",
    )
    return parser


def persist() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-p",
        "--persist",
        default=False,
        action="store_true",
        help="Store calibration results in database (default %(default)s)",
    )
    return parser


def author() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-a",
        "--author",
        nargs="+",
        default=None,
        help="Calibration author (default %(default)s)",
    )
    return parser


def upd() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-u",
        "--update",
        default=False,
        action="store_true",
        help="Update Zero Point in test photometer (default %(default)s)",
    )
    return parser


def wrzp() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-z",
        "--zero-point",
        type=float,
        metavar="<ZP>",
        required=True,
        help="Writed Zero Point to test photometer (default %(default)s)",
    )
    return parser

def nmsg() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "--num-messages",
        type=int,
        metavar="<N>",
        default=None,
        help="Number of messages to receive (default %(default)s)",
    )
    return parser


def ref() -> ArgumentParser:
    """Reference parser options"""
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-rE",
        "--ref-endpoint",
        type=vendpoint,
        default=None,
        metavar="<ref endpoint>",
        help="Reference photometer endpoint",
    )
    parser.add_argument(
        "-rM",
        "--ref-model",
        type=PhotModel,
        default=None,
        choices=PhotModel,
        help="Ref. photometer model, defaults to %(default)s",
    )
    parser.add_argument(
        "-rO",
        "--ref-old-proto",
        action="store_true",
        default=False,
        help="Use very old protocol instead of JSON, defaults to %(default)s",
    )
    parser.add_argument(
        "-rS",
        "--ref-sensor",
        type=Sensor,
        default=None,
        choices=Sensor,
        help="Reference phot sensor, defaults to %(default)s",
    )
    parser.add_argument(
        "-rR",
        "--ref-raw-message",
        action="store_true",
        default=False,
        help="Log raw messages, defaults to %(default)s",
    )
    return parser


def test() -> ArgumentParser:
    """Test parser options"""
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-tE",
        "--test-endpoint",
        type=vendpoint,
        default=None,
        metavar="<test endpoint>",
        help="Test photometer endpoint",
    )
    parser.add_argument(
        "-tM",
        "--test-model",
        type=PhotModel,
        default=None,
        choices=PhotModel,
        help="Test photometer model, defaults to %(default)s",
    )
    parser.add_argument(
        "-tO",
        "--test-old-proto",
        action="store_true",
        default=None,
        help="Use very old protocol instead of JSON, defaults to %(default)s",
    )
    parser.add_argument(
        "-tS",
        "--test-sensor",
        type=Sensor,
        default=None,
        choices=Sensor,
        help="Test photometer sensor, defaults to %(default)s",
    )
    parser.add_argument(
        "-tR",
        "--test-raw-message",
        action="store_true",
        default=False,
        help="Log raw messages, defaults to %(default)s",
    )
    return parser


def stats() -> ArgumentParser:
    """Statistics parser options"""
    parser = ArgumentParser(add_help=False)
    parser.add_argument("-S", "--samples", type=int, default=None, help="# samples in each round")
    parser.add_argument(
        "-C",
        "--central",
        type=CentralTendency,
        default=None,
        choices=CentralTendency,
        help="central tendency estimator, defaults to %(default)s",
    )
    parser.add_argument(
        "-R",
        "--rounds",
        type=int,
        default=None,
        metavar="<N>",
        help="Number of calibration rounds, defaults to %(default)s",
    )
    parser.add_argument(
        "-P",
        "--period",
        type=float,
        default=None,
        metavar="<sec.>",
        help="Wait period between rounds[s], defaults to %(default)s",
    )
    parser.add_argument(
        "-Z",
        "--zp-fict",
        type=float,
        default=None,
        metavar="<float>",
        help="Alternative ficticious Zero Point to use for both photometers, defaults to %(default)s",
    )
    parser.add_argument(
        "-O",
        "--zp-offset",
        type=float,
        default=None,
        metavar="<float>",
        help="Offset to add to calibrated Zero Point, defaults to %(default)s",
    )
    return parser
