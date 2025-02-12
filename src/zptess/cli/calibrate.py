# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
from datetime import timedelta
from argparse import Namespace, ArgumentParser
from typing import Sequence, Mapping

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
from .util.misc import log_phot_info, update_zp
from ..lib.photometer import VolatileCalibrator, PersistentCalibrator, Event, RoundStatsType
from ..lib import CentralTendency

# ----------------
# Module constants
# ----------------


DESCRIPTION = "TESS-W Reader tool"
HALF_SECOND = timedelta(seconds=0.5)

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# ------------------
# Auxiliar functions
# ------------------


def on_reading(role: Role, reading: Message) -> None:
    global controller
    log = logging.getLogger(role.tag())
    current = len(controller.buffer(role))
    total = controller.buffer(role).capacity()
    name = controller.phot_info[role]["name"]
    if current < total:
        log.info("%-9s waiting for enough samples, %03d remaining", name, total - current)


def on_round(current: int, mag_diff: float, zero_point: float, stats: RoundStatsType) -> None:
    global controller
    zp_abs = controller.zp_abs
    nrounds = controller.nrounds
    phot_info = controller.phot_info
    central = controller.central
    zp_fict = controller.zp_fict
    log.info("=" * 74)
    log.info(
        "%-10s %02d/%02d: New ZP = %0.2f = \u0394(ref-test) Mag (%0.2f) + ZP Abs (%0.2f)",
        "ROUND",
        current,
        nrounds,
        zero_point,
        mag_diff,
        zp_abs,
    )
    for role in (Role.REF, Role.TEST):
        tag = role.tag()
        name = phot_info[role]["name"]
        Ti = controller.ring[role][0]["tstamp"]
        Tf = controller.ring[role][-1]["tstamp"]
        T = (Tf - Ti).total_seconds()
        Ti = (Ti + HALF_SECOND).strftime("%H:%M:%S")
        Tf = (Tf + HALF_SECOND).strftime("%H:%M:%S")
        N = len(controller.ring[role])
        freq, stdev, mag = stats[role]
        log.info(
            "[%s] %-8s (%s-%s)[%4.1fs][%03d] %6s f = %0.3f Hz, \u03c3 = %0.3f Hz, m = %0.2f @ %0.2f",
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
        log.info("=" * 74)


def on_summary(
    zero_point_seq: Sequence[float],
    freq_seq: Mapping[Role, Sequence[float]],
    best_freq: Mapping[Role, float],
    best_freq_method: Mapping[Role, CentralTendency],
    best_mag: Mapping[Role, float],
    mag_diff: float,
    best_zero_point: float,
    best_zero_point_method: CentralTendency,
    final_zero_point: float,
    overlapping_windows: Mapping[Role, Sequence[float | None]],
) -> None:
    global controller
    log.info("#" * 74)
    log.info("Session = %s", controller.meas_session.strftime("%Y-%m-%dT%H:%M:%S"))
    log.info("Best ZP        list is %s", zero_point_seq)
    log.info("Best REF. Freq list is %s", freq_seq[Role.REF])
    log.info("Best TEST Freq list is %s", freq_seq[Role.TEST])
    log.info(
        "REF. Best Freq. = %0.3f Hz, Mag. = %0.2f, Diff %0.2f (%s)",
        best_freq[Role.REF],
        best_mag[Role.REF],
        0,
        best_freq_method[Role.REF],
    )
    log.info(
        "TEST Best Freq. = %0.3f Hz, Mag. = %0.2f, Diff %0.2f (%s)",
        best_freq[Role.TEST],
        best_mag[Role.TEST],
        mag_diff,
        best_freq_method[Role.TEST],
    )
    log.info(
        "Final TEST ZP (%0.2f) = Best ZP (%0.2f) (%s) + ZP offset (%0.2f)",
        final_zero_point,
        best_zero_point,
        best_zero_point_method,
        controller.zp_offset,
    )
    log.info(
        "Old TEST ZP = %0.2f, NEW TEST ZP = %0.2f",
        controller.phot_info[Role.TEST]["zp"],
        final_zero_point,
    )
    log.info("REF. rounds overlap \u0394T = %s", overlapping_windows[Role.REF])
    log.info("TEST rounds overlap \u0394T = %s", overlapping_windows[Role.TEST])
    log.info("#" * 74)


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
    if args.persist:
        controller = PersistentCalibrator(
            ref_params=ref_params, test_params=test_params, common_params=common_params
        )
        log.info("Logging results to a database")
    else:
        controller = VolatileCalibrator(
            ref_params=ref_params, test_params=test_params, common_params=common_params
        )
    pub.subscribe(on_reading, Event.READING)
    pub.subscribe(on_round, Event.ROUND)
    pub.subscribe(on_summary, Event.SUMMARY)
    await controller.init()
    await log_phot_info(controller, Role.REF)
    await log_phot_info(controller, Role.TEST)
    if args.dry_run:
        log.info("Dry run. Will stop here ...")
        return
    final_zero_point = await controller.calibrate()
    if args.update:
        await update_zp(controller, final_zero_point)
    else:
        msg = f"Zero Point {final_zero_point:.2f} not saved to {Role.TEST} {controller.phot_info[Role.TEST]['name']}"
        log.info(msg)
        await controller.not_updated(final_zero_point, msg)


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
