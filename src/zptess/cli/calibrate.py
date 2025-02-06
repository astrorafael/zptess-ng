# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
from typing import Mapping
from argparse import Namespace, ArgumentParser

# -------------------
# Third party imports
# -------------------

from pubsub import pub

from lica.asyncio.cli import execute
from lica.asyncio.photometer import Role, Message

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs
from .util.logging import log_phot_info
from ..lib.controller import Calibrator, FreqStatistics, Event


# ----------------
# Module constants
# ----------------

RoundStatsType = Mapping[Role, FreqStatistics]

DESCRIPTION = "TESS-W Reader tool"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# ------------------
# Auxiliar functions
# ------------------


def onReading(role: Role, reading: Message) -> None:
    global controller
    log = logging.getLogger(role.tag())
    current = len(controller.buffer(role))
    total = controller.buffer(role).capacity()
    name = controller.phot_info[role]["name"]
    if current < total:
        log.info("%-9s waiting for enough samples, %03d remaining", name, total - current)


def onRound(current: int, delta_mag: float, zero_point: float, stats: RoundStatsType) -> None:
    global controller
    zp_abs = controller.zp_abs
    nrounds = controller.nrounds
    phot_info = controller.phot_info
    central = controller.central
    zp_fict = controller.zp_fict
    log.info("=" * 72)
    log.info(
        "%-10s %02d/%02d: New ZP = %0.2f = \u0394(ref-test) Mag (%0.2f) + ZP Abs (%0.2f)",
        "ROUND",
        current,
        nrounds,
        zero_point,
        delta_mag,
        zp_abs,
    )
    for role in (Role.REF, Role.TEST):
        tag = role.tag()
        name = phot_info[role]["name"]
        Ti = controller.ring[role][0]["tstamp"]
        Tf = controller.ring[role][-1]["tstamp"]
        T = (Tf-Ti).total_seconds()
        Ti = Ti.strftime("%H:%M:%S")
        Tf = Tf.strftime("%H:%M:%S")
        N = len(controller.ring[role])
        freq, stdev, mag = stats[role]
        log.info(
            "[%s] %-8s (%s-%s)[%.1fs][%03d] %6s f = %0.3f Hz, \u03c3 = %0.3f Hz, m = %0.2f @ %0.2f",
            tag,
            name,
            Ti,
            Tf,
            T,
            N,
            central,
            freq,
            stdev,
            mag,
            zp_fict,
        )
    if current == nrounds:
        log.info("=" * 72)
   


# -----------------
# Auxiliary classes
# -----------------


# -------------------
# Auxiliary functions
# -------------------


async def cli_calib_test(args: Namespace) -> None:
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
    common_params = {
        "buffer": args.buffer,
        "persist": args.persist,
        "update": args.update,
        "central": args.central,
        "period": args.period,
        "zp_fict": args.zp_fict,
        "zp_offset": args.zp_offset,
        "rounds": args.rounds,
        "author": " ".join(args.author) if args.author else None,
    }
    controller = Calibrator(
        ref_params=ref_params, test_params=test_params, common_params=common_params
    )
    pub.subscribe(onReading, Event.READING)
    pub.subscribe(onRound, Event.ROUND)
    await controller.init()
    await log_phot_info(controller, Role.REF)
    await log_phot_info(controller, Role.TEST)
    if args.dry_run:
        log.info("Dry run. Will stop here ...")
    else:
        await controller.calibrate()


# -----------------
# CLI API functions
# -----------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command")
    p = subparser.add_parser(
        "test",
        parents=[
            prs.dry(),
            prs.stats(),
            prs.upd(),
            prs.persist(),
            prs.buf(),
            prs.author(),
            prs.ref(),
            prs.test(),
        ],
        help="Calibrate test photometer",
    )
    p.set_defaults(func=cli_calib_test)


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
