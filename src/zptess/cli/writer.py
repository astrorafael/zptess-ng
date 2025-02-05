# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
import asyncio
from argparse import Namespace, ArgumentParser

# -------------------
# Third party imports
# -------------------

from pubsub import pub

from lica.asyncio.cli import execute
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs
from ..lib.controller import Writer

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

# ------------------
# Auxiliar functions
# ------------------


async def log_phot_info(role: Role) -> None:
    global controller
    log = logging.getLogger(role.tag())
    phot_info = await controller.info(role)
    log.info("-"*40)
    for key, value in sorted(phot_info.items()):
        log.info("%-12s: %s", key.upper(), value)
    log.info("-"*40)


def onWritingZP(
    role: Role, zero_point: float, stored: float | None, timeout: bool, result: bool
) -> None:
    global controller
    log = logging.getLogger(role.tag())
    name = controller.phot_info[role]["name"]
    if result:
        log.info("[%s] ZP Write (%0.2f) verification Ok.", name, zero_point)
    elif timeout:
        log.critical("[%s] Failed contacting %s photometer", name, Role.TEST.tag())
    elif stored is None:
        log.critical("[%s] Operation failed for %s photometer", name, Role.TEST.tag())
    else:
        msg = (
            "ZP Write verification failed: ZP to Write (%0.2f) doesn't match ZP subsequently read (%0.2f)"
            % (zero_point, stored)
        )
        log.critical(msg)


# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


async def cli_update_zp(args: Namespace) -> None:
    global controller
    log = logging.getLogger(Role.TEST.tag())
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
    pub.subscribe(onWritingZP, "zp_writting_info")
    await log_phot_info(Role.TEST)
    name = controller.phot_info[Role.TEST]["name"]
    if args.dry_run:
        return
    zero_point = args.zero_point
    log.info("Updating ZP : %0.2f", args.zero_point)
    try:
        stored_zp = await controller.write_zp(zero_point)
    except asyncio.exceptions.TimeoutError:
        log.critical("[%s] Failed contacting %s photometer", name, Role.TEST.tag())
    except Exception as e:
        log.exception(e)
    else:
        if zero_point != stored_zp:
            log.critical(
                "ZP Write verification failed: ZP to Write (%0.2f) doesn't match ZP subsequently read (%0.2f)",
                zero_point, stored_zp
            )
        else:
            log.info("[%s] ZP Write (%0.2f) verification Ok.", name, zero_point)


# -----------------
# CLI API functions
# -----------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command")
    p = subparser.add_parser(
        "test", parents=[prs.dry(), prs.wrzp(), prs.test()], help="Read test photometer"
    )
    p.set_defaults(func=cli_update_zp)


async def cli_main(args: Namespace) -> None:
    if args.verbose:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("aiosqlite").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
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
