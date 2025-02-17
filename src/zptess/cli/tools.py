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
from lica.tabulate import paging

# --------------
# local imports
# -------------

from .. import __version__
from .util import parser as prs
from ..lib.controller.batch import Controller

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
    pass


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
