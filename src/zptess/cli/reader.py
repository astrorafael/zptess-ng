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


from argparse import Namespace
from typing import List

# -------------------
# Third party imports
# -------------------


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass
from sqlalchemy.ext.asyncio import async_sessionmaker

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
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




async def cli_read_ref(
    args: Namespace, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    pass

async def cli_read_test(
    args: Namespace, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
   pass

async def cli_read_both(
    args: Namespace, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    pass


# --------------
# main functions
# --------------


def add_args(parser):
    subparser = parser.add_subparsers(dest="command")
    p =subparser.add_parser("ref", parents=[prs.buffer()], help="Read reference photometer")
    p.set_defaults(func=cli_read_ref)
    p = subparser.add_parser("test", parents=[prs.buffer()], help="Read test photometer")
    p.set_defaults(func=cli_read_test)
    p = subparser.add_parser("both", parents=[prs.buffer()], help="read both photometers")
    p.set_defaults(func=cli_read_both)


async def cli_main(args: Namespace) -> None:
    if args.verbose:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("aiosqlite").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    async with engine.begin():
        await args.func(args, AsyncSession)
    await engine.dispose()



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
