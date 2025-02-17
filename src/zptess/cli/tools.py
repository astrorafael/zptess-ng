# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
from argparse import Namespace, ArgumentParser

# -------------------
# Third party imports
# -------------------

from lica.sqlalchemy import sqa_logging
from lica.validators import vdate, vdir
from lica.asyncio.cli import execute
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs
from ..lib.controller.batch import Controller

# ----------------
# Module constants
# ----------------

TSTAMP_FMT = "%Y-%m-%dT%H:%M:%S"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])


# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


# -----------------
# CLI API functions
# -----------------


async def cli_batch_begin(args: Namespace) -> None:
    batch = Controller()
    tstamp = await batch.open(comment="pepe")
    log.info("Opening batch %s", tstamp.strftime(TSTAMP_FMT))


async def cli_batch_end(args: Namespace) -> None:
    batch = Controller()
    t0, t1, N = await batch.close()
    log.info(
        "Closing batch [%s - %s] with %d calibrations",
        t0.strftime(TSTAMP_FMT),
        t1.strftime(TSTAMP_FMT),
        N,
    )


async def cli_batch_purge(args: Namespace) -> None:
    batch = Controller()
    N = await batch.purge()
    log.info("Purged %d batches with no summary calibration entries", N)

async def cli_batch_orphan(args: Namespace) -> None:
    batch = Controller()
    N = await batch.purge()
    log.info("Purged %d batches with no summary calibration entries", N)

async def cli_batch_export(args: Namespace) -> None:
    pass


def begin_add_args(parser: ArgumentParser):
    parser.add_argument(
        "-c",
        "--comment",
        type=str,
        nargs="+",
        default=None,
        help="Optional batch comment (default %(default)s)",
    )
    parser.set_defaults(func=cli_batch_begin)


def end_add_args(parser: ArgumentParser):
    parser.set_defaults(func=cli_batch_end)

def purge_add_args(parser: ArgumentParser):
    parser.set_defaults(func=cli_batch_purge)

def orphan_add_args(parser: ArgumentParser):
    parser.set_defaults(func=cli_batch_orphan)


def export_add_args(parser: ArgumentParser):
    ex1 = parser.add_mutually_exclusive_group(required=True)
    ex1.add_argument(
        "-b",
        "--begin-date",
        type=vdate,
        metavar="<YYYY-MM-DDTHH:MM:SS>",
        default=None,
        help="by begin",
    )
    ex1.add_argument("-l", "--latest", action="store_true", help="latest closed batch")
    ex1.add_argument("-a", "--all", action="store_true", help="all closed batches")
    parser.add_argument("-d", "--base-dir", type=vdir, default=".", help="Base dir for the export")
    parser.add_argument("-e", "--email", action="store_true", help="Send results by email")
    parser.add_argument(
        "-u",
        "--updated",
        action="store_true",
        help="Do action only when ZP updated flag is True|False",
    )
    parser.set_defaults(func=cli_batch_export)


async def cli_main(args: Namespace) -> None:
    sqa_logging(args)
    await args.func(args)


def begin():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=begin_add_args,
        name=__name__,
        version=__version__,
        description="Begin calibration batch",
    )


def end():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=end_add_args,
        name=__name__,
        version=__version__,
        description="End calibration batch",
    )


def purge():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=purge_add_args,
        name=__name__,
        version=__version__,
        description="Purge batches with no calibrations",
    )

def orphan():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=orphan_add_args,
        name=__name__,
        version=__version__,
        description="Number of orphan calibrations that do not belong to a batch",
    )


def export():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=export_add_args,
        name=__name__,
        version=__version__,
        description="Export calibrations in a batch",
    )
