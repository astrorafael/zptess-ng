# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import os

from argparse import ArgumentParser

# ---------------------------
# Third-party library imports
# ----------------------------

from lica.validators import vdir
from lica.asyncio.photometer import Model as PhotModel, Sensor

#--------------
# local imports
# -------------

from .misc import mkendpoint

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


def buffer() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-b",
        "--buffered",
        default=False,
        action="store_true",
        help="Use circular buffer (default %(default)s)",
    )
    return parser


def ref() -> ArgumentParser:
    """Reference parser options"""
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-rE",
        "--ref-endpoint",
        type=mkendpoint,
        default=None,
        metavar="<ref endpoint>",
        help="Reference photometer endpoint",
    )
    parser.add_argument(
        "-rM",
        "--ref-model",
        type=PhotModel,
        default=PhotModel.TESSW.name,
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
        default=Sensor.TSL237,
        choices=Sensor,
        help="Reference phot sensor, defaults to %(default)s",
    )

    return parser


def test() -> ArgumentParser:
    """Test parser options"""
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-tE",
        "--test-endpoint",
        type=mkendpoint,
        default=None,
        metavar="<test endpoint>",
        help="Test photometer endpoint",
    )
    parser.add_argument(
        "-tM",
        "--test-model",
        type=PhotModel,
        default=PhotModel.TESSW,
        choices=PhotModel,
        help="Test photometer model, defaults to %(default)s",
    )
    parser.add_argument(
        "-tO",
        "--test-old-proto",
        action="store_true",
        default=False,
        help="Use very old protocol instead of JSON, defaults to %(default)s",
    )
    parser.add_argument(
        "-tS",
        "--test-sensor",
        type=Sensor,
        default=Sensor.TSL237,
        choices=Sensor,
        help="Test photometer sensor, defaults to %(default)s",
    )
    return parser
