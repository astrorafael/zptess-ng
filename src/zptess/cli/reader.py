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
from typing import Mapping, Any
from argparse import Namespace, ArgumentParser

# -------------------
# Third party imports
# -------------------

from pubsub import pub

#from lica.cli import execute
from lica.asyncio.cli import execute
from lica.asyncio.photometer import Role

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
controller = None

# ------------------
# Auxiliar functions
# ------------------


async def log_phot_info(role: Role) -> None:
    global controller
    log = logging.getLogger(role.tag())
    phot_info = await controller.info(role)
    for key, value in sorted(phot_info.items()):
        log.info("%-12s: %s", key.upper(), value)


def onReading(role: Role, reading: Mapping[str, Any]) -> None:
    global controller
    log = logging.getLogger(role.tag())
    name = controller.phot_info[role]["name"]
    line = f"{name:9s} [{reading.get('seq')}] f={reading['freq']} Hz, tbox={reading['tamb']}, tsky={reading['tsky']}"
    log.info(line)


# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


async def log_messages(role: Role, num: int | None = None) -> None:
    global controller
    log = logging.getLogger(role.tag())
    name = controller.phot_info[role]["name"]
    async for role, msg in controller.receive(role, num):
        line = f"{name:9s} [{msg.get('seq')}] f={msg['freq']} Hz, tbox={msg['tamb']}, tsky={msg['tsky']}"
        log.info(line)


async def cli_read_ref(args: Namespace) -> None:
    global controller
    ref_params = {
        "model": args.ref_model,
        "sensor": args.ref_sensor,
        "endpoint": args.ref_endpoint,
        "old_proto": args.ref_old_proto,
        "log_level": logging.INFO if args.ref_raw_message else logging.WARN,
    }
    controller = Reader(
        ref_params=ref_params,
    )
    pub.subscribe(onReading, "reading_info")
    await controller.init()
    await log_phot_info(Role.REF)
    if args.dry_run:
        return
    await log_messages(Role.REF, args.num_messages)


async def cli_read_test(args: Namespace) -> None:
    global controller
    test_params = {
        "model": args.test_model,
        "sensor": args.test_sensor,
        "endpoint": args.test_endpoint,
        "old_proto": args.test_old_proto,
        "log_level": logging.INFO if args.test_raw_message else logging.WARN,
    }
    controller = Reader(
        test_params=test_params,
    )
    pub.subscribe(onReading, "reading_info")
    await controller.init()
    await log_phot_info(Role.TEST)
    if args.dry_run:
        return
    await log_messages(Role.TEST, args.num_messages)


async def cli_read_both(args: Namespace) -> None:
    global controller
    ref_params = {
        "model": args.ref_model,
        "sensor": args.ref_sensor,
        "endpoint": args.ref_endpoint,
        "old_proto": args.ref_old_proto,
        "log_level": logging.INFO if args.ref_raw_message else logging.WARN,
    }
    test_params = {
        "model": args.test_model,
        "sensor": args.test_sensor,
        "endpoint": args.test_endpoint,
        "old_proto": args.test_old_proto,
        "log_level": logging.INFO if args.test_raw_message else logging.WARN,
    }
    controller = Reader(
        ref_params=ref_params,
        test_params=test_params,
    )
    pub.subscribe(onReading, "reading_info")
    await controller.init()
    await log_phot_info(Role.REF)
    await log_phot_info(Role.TEST)
    if args.dry_run:
        return
    await asyncio.gather(
        log_messages(Role.REF, args.num_messages), log_messages(Role.TEST, args.num_messages)
    )


# -----------------
# CLI API functions
# -----------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command")
    p = subparser.add_parser(
        "ref", parents=[prs.dry(), prs.nmsg(), prs.ref()], help="Read reference photometer"
    )
    p.set_defaults(func=cli_read_ref)
    p = subparser.add_parser(
        "test", parents=[prs.dry(), prs.nmsg(), prs.test()], help="Read test photometer"
    )
    p.set_defaults(func=cli_read_test)
    p = subparser.add_parser(
        "both",
        parents=[
            prs.dry(),
            prs.nmsg(),
            prs.ref(),
            prs.test(),
        ],
        help="read both photometers",
    )
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
    execute(
        main_func=cli_main,
        add_args_func=add_args,
        name=__name__,
        version=__version__,
        description=DESCRIPTION,
    )


if __name__ == "__main__":
    main()
