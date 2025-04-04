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
from lica.asyncio.cli import execute
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .. import __version__
from ..lib.controller.photometer import Writer
from .util.misc import log_phot_info, update_zp
from .util import parser as prs

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Zero Point update tool"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])
controller = None

# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


async def cli_update_zp(args: Namespace) -> None:
    global controller

    test_params = {
        "model": args.test_model,
        "sensor": args.test_sensor,
        "endpoint": args.test_endpoint,
        "old_proto": args.test_old_proto,
        "log_level": logging.INFO if args.test_raw_message else logging.WARN,
    }
    controller = Writer(
        test_params=test_params,
    )
    await controller.init()
    await log_phot_info(controller, Role.TEST)
    if args.dry_run:
        return
    await update_zp(controller, args.zero_point)

# -----------------
# CLI API functions
# -----------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command", required=True)
    p = subparser.add_parser(
        "test", parents=[prs.wrzp(), prs.test()], help="Read test photometer"
    )
    p.add_argument(
        "-d", "--dry-run", action="store_true", help="Do not update photometer"
    )
    p.set_defaults(func=cli_update_zp)


async def cli_main(args: Namespace) -> None:
    sqa_logging(args)
    await args.func(args)


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
