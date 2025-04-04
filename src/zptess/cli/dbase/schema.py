# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
from argparse import ArgumentParser, Namespace

# ------------------
# SQLAlchemy imports
# -------------------

from lica.asyncio.cli import execute
from lica.sqlalchemy import sqa_logging
from lica.sqlalchemy.asyncio.dbase import engine, Model

# --------------
# local imports
# -------------

from ... import __version__

# We must pull one model to make it work
from ...lib.dbase.model import Config  # noqa: F401

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Calibration Database initial schema generation tool"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# -------------------
# Auxiliary functions
# -------------------


async def schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    await engine.dispose()


async def cli_main(args: Namespace) -> None:
    sqa_logging(args)
    await schema()


def add_args(parser: ArgumentParser) -> None:
    pass


def main():
    """The main entry point specified by pyproject.toml"""
    execute(
        main_func=cli_main,
        add_args_func=add_args,
        name=__name__,
        version=__version__,
        description=DESCRIPTION,
    )


if __name__ == "__main__":
    main()
