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

from datetime import datetime
from typing import Sequence, Tuple, Any

# -------------------
# Third party imports
# -------------------

from lica.sqlalchemy.asyncio.dbase import AsyncSession

# --------------
# local imports
# -------------

from ..lib.dbase.model import SummaryView, RoundView, SampleView
from sqlalchemy import select, func, cast, Integer


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


class Exporter:
    def __init__(
        self,
        base_dir: str,
        filename_prefix: str,
        begin_tstamp: datetime = None,
        end_tstamp: datetime = None,
    ):
        self.begin_tstamp = begin_tstamp
        self.end_tstamp = end_tstamp
        self.base_dir = base_dir
        self.filename_prefix = filename_prefix

    async def query_summaries(self) -> Sequence[Tuple[Any]]:
        async with AsyncSession() as session:
            async with session.begin():
                t0 = self.begin_tstamp
                t1 = self.end_tstamp
                q = select(
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
                if t0 is not None:
                    q = q.where(
                        SummaryView.session.between(t0, t1), SummaryView.upd_flag == True  # noqa: E712
                    ).order_by(cast(func.substr(SummaryView.name, 6), Integer), SummaryView.session)
                else:
                    q = q.where(
                        SummaryView.name.like("stars%"), SummaryView.upd_flag == True  # noqa: E712
                    ).order_by(cast(func.substr(SummaryView.name, 6), Integer), SummaryView.session)
                summaries = (await session.execute(q)).all()
                summaries = self._filter_latest_summary(summaries)
        return summaries

    async def query_rounds(self) -> Sequence[Tuple[Any]]:
        async with AsyncSession() as session:
            async with session.begin():
                t0 = self.begin_tstamp
                t1 = self.end_tstamp
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

    async def query_samples(self) -> Sequence[Tuple[Any]]:
        async with AsyncSession() as session:
            async with session.begin():
                t0 = self.begin_tstamp
                t1 = self.end_tstamp
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

    def _filter_latest_summary(self, summaries: Sequence[Tuple[Any]]) -> Sequence[Tuple[Any]]:
        # group by photometer name
        grouped = itertools.groupby(summaries, key=lambda summary: summary[1])
        result = list()
        for name, group in grouped:
            group = tuple(group)
            result.append(
                group[-1]
            )  # Since they are sorted by ascending order, choose the last one
            if len(group) > 1:
                log.warn("%s has %d summaries, choosing the most recent session", name, len(group))
        return result

    def export_summaries(self, summaries: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"summary_{self.filename_preffix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(SUMMARY_EXPORT_HEADERS)
            for summary in summaries:
                csv_writer.writerow(summary)

    def export_rounds(self, rounds: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"rounds_{self.filename_preffix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(ROUND_EXPORT_HEADERS)
            for round_ in rounds:
                csv_writer.writerow(round_)

    async def export_samples(self, samples: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"samples_{self.filename_preffix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(SAMPLE_EXPORT_HEADERS)
            for sample in samples:
                csv_writer.writerow(sample)
