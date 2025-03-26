# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import os
import asyncio
import logging

from argparse import Namespace, ArgumentParser

# -------------------
# Third party imports
# -------------------

from lica.sqlalchemy import sqa_logging
from lica.asyncio.cli import execute
from lica.tabulate import paging

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs

from ..lib.controller.batch import Controller
from ..lib.controller.exporter import Exporter


# ----------------
# Module constants
# ----------------

TSTAMP_FMT = "%Y-%m-%dT%H:%M:%S"

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

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
        exporter = Exporter(base_dir=args.base_dir, filename_prefix="all")
        log.info("exporting to directory %s", args.base_dir)
        summaries = await exporter.query_summaries()
        # This is not necessary in a CLI application, just to show how it should be done in a GUI
        await asyncio.to_thread(exporter.export_summaries, summaries)
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
            base_dir = os.path.join(args.base_dir, filename_preffix)
            log.info("exporting to directory %s", base_dir)
            os.makedirs(base_dir, exist_ok=True)
            exporter = Exporter(
                base_dir=base_dir,
                filename_prefix=filename_preffix,
                begin_tstamp=batch.begin_tstamp,
                end_tstamp=batch.end_tstamp,
            )
            summaries = await exporter.query_summaries()
            await asyncio.to_thread(exporter.export_summaries, summaries)
            rounds = await exporter.query_rounds()
            await asyncio.to_thread(exporter.export_rounds, rounds)
            samples = await exporter.query_rounds()
            await asyncio.to_thread(exporter.export_samples, samples)
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
