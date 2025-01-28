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

from lica.cli import async_execute
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs
from ..lib.controller import Reader

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Reader tool"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# ------------------
# Auxiliar functions
# ------------------


# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


async def cli_read_ref(args: Namespace) -> None:
    controller = Reader(
        which=(args.command), 
        models={Role.REF: args.ref_model}, 
        sensors={Role.REF: args.ref_sensor},
        buffered=args.buffered,
        query=args.query
    )
    await controller.init()
    await controller.start()


async def cli_read_test(args: Namespace) -> None:
    controller = Reader(
        which=(args.command),
        models={Role.TEST: args.test_model},
        sensors={Role.TEST: args.test_sensor},
        query=args.query
    )
    await controller.init()
    await controller.start()


async def cli_read_both(args: Namespace) -> None:
    controller = Reader(
        which=("ref", "test"),
        models={Role.REF: args.ref_model, Role.TEST: args.test_model},
        sensors={Role.REF: args.ref_sensor, Role.TEST: args.test_sensor},
        query=args.query
    )
    await controller.init()
    await controller.start()


# -----------------
# CLI API functions
# -----------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command")
    p = subparser.add_parser("ref", parents=[prs.info(), prs.buffer(), prs.ref()], help="Read reference photometer")
    p.set_defaults(func=cli_read_ref)
    p = subparser.add_parser("test", parents=[prs.info(), prs.buffer(), prs.test()], help="Read test photometer")
    p.set_defaults(func=cli_read_test)
    p = subparser.add_parser("both", parents=[prs.info(), prs.buffer(), prs.ref(), prs.test()], help="read both photometers")
    p.set_defaults(func=cli_read_both)


async def cli_main(args: Namespace) -> None:
    if args.verbose:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("aiosqlite").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    await args.func(args)


def main():
    """The main entry point specified by pyproject.toml"""
    async_execute(
        main_func=cli_main,
        add_args_func=add_args,
        name=__name__,
        version=__version__,
        description=DESCRIPTION,
    )


if __name__ == "__main__":
    main()
