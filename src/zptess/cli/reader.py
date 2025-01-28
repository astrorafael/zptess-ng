# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------


import logging
from datetime import datetime


from argparse import Namespace, ArgumentParser
from typing import List

# -------------------
# Third party imports
# -------------------

from lica.asyncio.photometer import Role
from lica.validators import vdate
from lica.cli import async_execute

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Reader tool"

# -----------------------
# Module global variables
# -----------------------

# get the root logger
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
    log.info(args)


async def cli_read_test(args: Namespace) -> None:
    log.info(args)


async def cli_read_both(args: Namespace) -> None:
    log.info(args)


# --------------
# main functions
# --------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command")
    p = subparser.add_parser("ref", parents=[prs.ref()], help="Read reference photometer")
    p.set_defaults(func=cli_read_ref)
    p = subparser.add_parser("test", parents=[prs.test()], help="Read test photometer")
    p.set_defaults(func=cli_read_test)
    p = subparser.add_parser("both", parents=[prs.ref(), prs.test()], help="read both photometers")
    p.set_defaults(func=cli_read_both)


async def cli_main(args: Namespace) -> None:
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
