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
from argparse import Namespace, ArgumentParser

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
from ..lib.dbase.model import Photometer, Summary, Round, Sample, SummaryView
from sqlalchemy import select, func, cast, Integer

# ----------------
# Module constants
# ----------------

TSTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
EXPORT_HEADERS = (
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
    batch_ctrl = Controller()
    if args.begin_date:
        batch = await batch_ctrl.by_date(args.begin_date)
    elif args.latest:
        batch = await batch_ctrl.latest()
    else:
        raise NotImplementedError("Not yet available, please, be patient ...")
    if batch is None:
        log.info("No batch is available")
        return
    filename = f"from_{batch.begin_tstamp}_to_{batch.end_tstamp}".replace("-", "").replace(":", "")
    export_dir = os.path.join(args.base_dir, filename)
    log.info("exporting to directory %s", export_dir)
    os.makedirs(export_dir, exist_ok=True)
    csv_path = os.path.join(export_dir, f"summary_{filename}.csv")
    log.info("Fetching summaries for batch %s", batch)
    async with AsyncSession() as session:
        async with session.begin():
            t0 = batch.begin_tstamp
            t1 = batch.end_tstamp
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
                .order_by(cast(func.substr(SummaryView.name, 6), Integer))
            )
            summaries = (await session.execute(q)).all()
    with open(csv_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerow(EXPORT_HEADERS)
        for summary in summaries:
            csv_writer.writerow(summary)


    


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
