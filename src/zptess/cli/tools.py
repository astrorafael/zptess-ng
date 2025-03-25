# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import os
import csv
import logging
import itertools

from argparse import Namespace, ArgumentParser
from datetime import datetime
from typing import Sequence

# -------------------
# Third party imports
# -------------------

from lica.sqlalchemy import sqa_logging
from lica.sqlalchemy.asyncio.dbase import AsyncSession
from lica.asyncio.cli import execute
from lica.tabulate import paging

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs


from ..lib.controller.batch import Controller
from ..lib.dbase.model import Batch, SummaryView, RoundView, SampleView
from sqlalchemy import select, func, cast, Integer

# ----------------
# Module constants
# ----------------

TSTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
SUMMARY_EXPORT_HEADERS = (
    "model",
    "name",
    "mac",
    "firmware",
    "sensor",
    "session",
    "calibration",
    "calversion",
    "ref_mag",
    "ref_freq",
    "test_mag",
    "test_freq",
    "mag_diff",
    "raw_zero_point",
    "offset",
    "zero_point",
    "prev_zp",
    "filter",
    "plug",
    "box",
    "collector",
    "author",
    "comment",
)

ROUND_EXPORT_HEADERS = (
    "Model",
    "Name",
    "MAC",
    "Session (UTC)",
    "Role",
    "Round",
    "Freq (Hz)",
    "\u03c3 (Hz)",
    "Mag",
    "ZP",
    "# Samples",
    "\u0394T (s.)",
)

SAMPLE_EXPORT_HEADERS = (
    "Model",
    "Name",
    "MAC",
    "Session (UTC)",
    "Role",
    "Round",
    "Timestamp",
    "Freq (Hz)",
    "Box Temp (\u2103)",
    "Sequence #",
)

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


async def query_summaries(begin_tstamp: datetime, end_tstamp: datetime) -> Sequence[SummaryView]:
    async with AsyncSession() as session:
        async with session.begin():
            t0 = begin_tstamp
            t1 = end_tstamp
            q = (
                select(
                    SummaryView.model,
                    SummaryView.name,
                    SummaryView.mac,
                    SummaryView.firmware,
                    SummaryView.sensor,
                    SummaryView.session,
                    SummaryView.calibration,
                    SummaryView.calversion,
                    SummaryView.ref_mag,
                    SummaryView.ref_freq,
                    SummaryView.test_freq,
                    SummaryView.test_mag,
                    SummaryView.mag_diff,
                    SummaryView.raw_zero_point,
                    SummaryView.zp_offset,
                    SummaryView.zero_point,
                    SummaryView.prev_zp,
                    SummaryView.filter,
                    SummaryView.plug,
                    SummaryView.box,
                    SummaryView.collector,
                    SummaryView.author,
                    SummaryView.comment,
                )
                .where(SummaryView.session.between(t0, t1), SummaryView.upd_flag == True)  # noqa: E712
                .order_by(cast(func.substr(SummaryView.name, 6), Integer), SummaryView.session)
            )
            summaries = (await session.execute(q)).all()
    return summaries


async def query_all_summaries() -> Sequence[SummaryView]:
    async with AsyncSession() as session:
        async with session.begin():
            q = (
                select(
                    SummaryView.model,
                    SummaryView.name,
                    SummaryView.mac,
                    SummaryView.firmware,
                    SummaryView.sensor,
                    SummaryView.session,
                    SummaryView.calibration,
                    SummaryView.calversion,
                    SummaryView.ref_mag,
                    SummaryView.ref_freq,
                    SummaryView.test_freq,
                    SummaryView.test_mag,
                    SummaryView.mag_diff,
                    SummaryView.raw_zero_point,
                    SummaryView.zp_offset,
                    SummaryView.zero_point,
                    SummaryView.prev_zp,
                    SummaryView.filter,
                    SummaryView.plug,
                    SummaryView.box,
                    SummaryView.collector,
                    SummaryView.author,
                    SummaryView.comment,
                )
                .where(SummaryView.name.like("stars%"), SummaryView.upd_flag == True)  # noqa: E712
                .order_by(cast(func.substr(SummaryView.name, 6), Integer), SummaryView.session)
            )
            summaries = (await session.execute(q)).all()
    return summaries


def filter_latest_summary(summaries: Sequence[SummaryView]) -> Sequence[SummaryView]:
    # group by photometer name
    grouped = itertools.groupby(summaries, key=lambda summary: summary[1])
    result = list()
    for name, group in grouped:
        group = tuple(group)
        result.append(group[-1])  # Since they are sorted by ascending order, choose the last one
        if len(group) > 1:
            log.warn("%s has %d summaries, choosing the most recent session", name, len(group))
    return result


async def export_summaries(base_dir: str, filename_preffix: str, batch: Batch) -> None:
    log.info("Fetching summaries for batch %s", batch)
    summaries = await query_summaries(batch.begin_tstamp, batch.end_tstamp)
    csv_path = os.path.join(base_dir, f"summary_{filename_preffix}.csv")
    log.info("exporting %s", os.path.basename(csv_path))
    with open(csv_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=";")
        csv_writer.writerow(SUMMARY_EXPORT_HEADERS)
        for summary in summaries:
            csv_writer.writerow(summary)


async def export_all_summaries(base_dir: str, filename_preffix: str) -> None:
    log.info("Fetching ALL summaries")
    summaries = await query_all_summaries()
    summaries = filter_latest_summary(summaries)
    csv_path = os.path.join(base_dir, f"summary_{filename_preffix}.csv")
    log.info("exporting %s", os.path.basename(csv_path))
    with open(csv_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=";")
        csv_writer.writerow(SUMMARY_EXPORT_HEADERS)
        for summary in summaries:
            csv_writer.writerow(summary)


async def query_rounds(begin_tstamp: datetime, end_tstamp: datetime) -> Sequence[RoundView]:
    async with AsyncSession() as session:
        async with session.begin():
            t0 = begin_tstamp
            t1 = end_tstamp
            q = (
                select(
                    RoundView.model,
                    RoundView.name,
                    RoundView.mac,
                    RoundView.session,
                    RoundView.role,
                    RoundView.round,
                    RoundView.freq,
                    RoundView.stddev,
                    RoundView.mag,
                    RoundView.zero_point,
                    RoundView.nsamples,
                    RoundView.duration,
                )
                # complicated filter because stars3 always has upd_flag = False
                .where(
                    RoundView.session.between(t0, t1)
                    & (
                        (RoundView.upd_flag == True)  # noqa: E712
                        | ((RoundView.upd_flag == False) & (RoundView.name == "stars3"))  # noqa: E712
                    )
                )  
                .order_by(RoundView.session, RoundView.round)
            )
            rounds = (await session.execute(q)).all()
    return rounds


async def export_rounds(base_dir: str, filename_preffix: str, batch: Batch) -> None:
    log.info("Fetching rounds for batch %s", batch)
    rounds = await query_rounds(batch.begin_tstamp, batch.end_tstamp)
    csv_path = os.path.join(base_dir, f"rounds_{filename_preffix}.csv")
    log.info("exporting %s", os.path.basename(csv_path))
    with open(csv_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=";")
        csv_writer.writerow(ROUND_EXPORT_HEADERS)
        for round_ in rounds:
            csv_writer.writerow(round_)


async def query_samples(begin_tstamp: datetime, end_tstamp: datetime) -> Sequence[SampleView]:
    async with AsyncSession() as session:
        async with session.begin():
            t0 = begin_tstamp
            t1 = end_tstamp
            q = (
                select(
                    SampleView.model,
                    SampleView.name,
                    SampleView.mac,
                    SampleView.session,
                    SampleView.role,
                    SampleView.round,
                    SampleView.tstamp,
                    SampleView.freq,
                    SampleView.temp_box,
                    SampleView.seq,
                )
                # complicated filter because stars3 always has upd_flag = False
                .where(
                    SampleView.session.between(t0, t1)
                    & (
                        (SampleView.upd_flag == True)  # noqa: E712
                        | ((SampleView.upd_flag == False) & (SampleView.name == "stars3"))  # noqa: E712
                    )
                )  
                .order_by(SampleView.session, SampleView.round, SampleView.tstamp)
            )
            rounds = (await session.execute(q)).all()
    return rounds


async def export_samples(base_dir: str, filename_preffix: str, batch: Batch) -> None:
    log.info("Fetching samples for batch %s", batch)
    samples = await query_samples(batch.begin_tstamp, batch.end_tstamp)
    csv_path = os.path.join(base_dir, f"samples_{filename_preffix}.csv")
    log.info("exporting %s", os.path.basename(csv_path))
    with open(csv_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=";")
        csv_writer.writerow(SAMPLE_EXPORT_HEADERS)
        for sample in samples:
            csv_writer.writerow(sample)


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
    orphans = await batch.orphan()
    log.info("%d orphan summaries not belonging to a batch", len(orphans))
    if args.list:
        for i, item in enumerate(sorted(orphans), start=1):
            log.info("[%03d] %s", i, item)


async def cli_batch_view(args: Namespace) -> None:
    batch = Controller()
    HEADERS = ("Begin (UTC)", "End (UTC)", "# Sessions", "Emailed?", "Comment")
    iterable = await batch.view()
    paging(iterable, HEADERS, page_size=args.page_size, table_fmt=args.table_format)


async def cli_batch_export(args: Namespace) -> None:
    if args.all:
        export_dir = args.base_dir
        log.info("exporting to directory %s", export_dir)
        await export_all_summaries(export_dir, "all")
    else:
        batch_ctrl = Controller()
        batch = (
            await batch_ctrl.by_date(args.begin_date)
            if args.begin_date
            else await batch_ctrl.latest()
        )
        if batch is not None:
            t0 = batch.begin_tstamp.strftime("%Y%m%d")
            t1 = batch.end_tstamp.strftime("%Y%m%d")
            filename_preffix = f"from_{t0}_to_{t1}"
            export_dir = os.path.join(args.base_dir, filename_preffix)
            log.info("exporting to directory %s", export_dir)
            os.makedirs(export_dir, exist_ok=True)
            await export_summaries(export_dir, filename_preffix, batch)
            await export_rounds(export_dir, filename_preffix, batch)
            await export_samples(export_dir, filename_preffix, batch)
        else:
            log.info("No batch is available")


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest="command", required=True)
    p = subparser.add_parser(
        "begin",
        parents=[prs.comm()],
        help="Begin new calibration batch",
    )
    p.set_defaults(func=cli_batch_begin)
    p = subparser.add_parser(
        "end",
        parents=[],
        help="End current calibration batch",
    )
    p.set_defaults(func=cli_batch_end)
    p = subparser.add_parser(
        "purge",
        parents=[],
        help="Purge empty calibration batches",
    )
    p.set_defaults(func=cli_batch_purge)
    p = subparser.add_parser(
        "view",
        parents=[prs.tbl()],
        help="List calibration batches",
    )
    p.set_defaults(func=cli_batch_view)
    p = subparser.add_parser(
        "orphan",
        parents=[prs.lst()],
        help="List calibration mummaries not belonging to any batch",
    )
    p.set_defaults(func=cli_batch_orphan)
    p = subparser.add_parser(
        "export",
        parents=[prs.odir(), prs.expor()],
        help="Export calibration batch to CSV files",
    )
    p.set_defaults(func=cli_batch_export)


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
        description="Batch calibration management tools",
    )
