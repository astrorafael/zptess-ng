# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------


import math
import logging
from datetime import datetime
import statistics

from argparse import ArgumentParser, Namespace
from typing import List

# -------------------
# Third party imports
# -------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass
from sqlalchemy.ext.asyncio import async_sessionmaker

from lica.sqlalchemy import sqa_logging
from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer import Role
from lica.validators import vdate
from lica.asyncio.cli import execute

# --------------
# local imports
# -------------

from ... import __version__
from ...lib.dbase.model import Round, Photometer, Sample, Summary
from ...lib import CentralTendency

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Calibration Database Quality Assurance tool"

_CENTRAL_MAP = {
    CentralTendency.MEAN: statistics.mean,
    CentralTendency.MEDIAN: statistics.median,
    CentralTendency.MODE: statistics.mode,
}

# -----------------------
# Module global variables
# -----------------------

# get the root logger
log = logging.getLogger(__name__.split(".")[-1])

# ------------------
# Auxiliar functions
# ------------------


def central(method: CentralTendency):
    assert method in CentralTendency, f"Statistics central method {method} is not supported"
    return _CENTRAL_MAP[method]


def magnitude(zp, freq):
    return zp - 2.5 * math.log10(freq)


# -----------------
# Auxiliary classes
# -----------------


class DbgPhotometer(Photometer):
    pass


class DbgSummary(Summary):
    def assert_nrounds(self, rounds):
        N = len(rounds)
        if not (self.nrounds is None or self.nrounds == N):
            log.error(
                "[%s] [%s] [%s] Summary rounds. computed = %d, stored = %d",
                self.n,
                self.m,
                self.s,
                N,
                self.nrounds,
            )

    def assert_fict_zp(self, rounds, default: float = 20.50):
        if not all([r.zp_fict == rounds[0].zp_fict for r in rounds]):
            log.error(
                "[%s] [%s] [%s] Summary. Fict ZP: All not are equal %s",
                self.n,
                self.m,
                self.s,
                [r.zp_fict for r in rounds],
            )
        if rounds:
            zp_fict = rounds[0].zp_fict
            if rounds[0].zp_fict != default:
                log.warn(
                    "[%s] [%s] [%s] Summary. Ficticious ZP (%s) is not %s",
                    self.n,
                    self.m,
                    self.s,
                    zp_fict,
                    default,
                )

    def assert_freq_from_rounds(self, rounds):
        """
        Asserts that the computed central frequency from the several frequency rounds
        using the central method also specied in the Summary table
        equals the central frequency stored in the Summary table.
        """
        freqs = [r.freq for r in rounds]
        central_func = central(self.freq_method)
        freq = central_func(freqs)
        if not math.fabs(freq - self.freq) < 0.0005:
            log.error(
                "[%s] [%s] [%s]  Summary Frequency: computed =%.3f, stored =%.3f, \u0394 = %.3f",
                self.n,
                self.m,
                self.s,
                freq,
                self.freq,
                freq - self.freq,
            )
        return freq

    def assert_mag_from_rounds(self, rounds, freq):
        zp_fict = rounds[0].zp_fict
        mag = magnitude(zp_fict, freq)
        if not math.fabs(mag - self.mag) < 0.005:
            log.warn(
                "[%s] [%s] [%s]  Summary Magnitudes: computed =%f from f=%.3f & zp=%.2f, stored mag=%f from stored f=%.3f \u0394 = %.3f",
                self.n,
                self.m,
                self.s,
                mag,
                freq,
                zp_fict,
                self.mag,
                self.freq,
                mag - self.mag,
            )

    def assert_zp_from_rounds(self, rounds):
        """
        Asserts that the computed central zero point from the several zero point rounds
        using the central method also specied in the Summary table
        equals the central zero_point stored in the Summary table (minus the offset).
        """
        zps = [r.zero_point for r in rounds]
        central_func = central(self.zero_point_method)
        zp = central_func(zps) + self.zp_offset
        if not math.fabs(zp - self.zero_point) < 0.005:
            log.warn(
                "[%s] [%s] [%s]  Summary Zero Points: computed zp=%f, stored zp=%f",
                self.n,
                self.m,
                self.s,
                zp,
                self.zero_point,
            )

    async def check(self, photometer):
        self.n = photometer.name
        self.m = photometer.mac
        self.s = self.session
        rounds = await self.awaitable_attrs.rounds
        log.info("[%s] [%s] [%s] Summary assert_nounds", self.n, self.m, self.s)
        self.assert_nrounds(rounds)
        log.info("[%s] [%s] [%s] Summary assert_fict_zp", self.n, self.m, self.s)
        self.assert_fict_zp(rounds)
        if self.nrounds is not None:
            log.info("[%s] [%s] [%s] Summary assert_freq_from_rounds", self.n, self.m, self.s)
            freq = self.assert_freq_from_rounds(rounds)
            self.assert_mag_from_rounds(rounds, freq)
            if self.role == Role.TEST:
                log.info("[%s] [%s] [%s] Summary assert_zp_from_rounds", self.n, self.m, self.s)
                self.assert_zp_from_rounds(rounds)


class DbgRound(Round):
    def assert_round_magnitude(self) -> float:
        mag = self.zp_fict - 2.5 * math.log10(self.freq)
        if not math.fabs(self.mag - mag) < 0.005:
            log.error(
                "[%s] [%s] [%s] Round #%d. Magnitudes: computed = %f @ zp = %f, stored = %f",
                self.n,
                self.m,
                self.s,
                self.seq,
                mag,
                self.zp_fict,
                self.mag,
            )

    def assert_freq_from_samples(self, samples) -> float:
        """Computes the central frequnency from its samples"""
        freqs = [s.freq for s in samples]
        central_func = central(self.central)
        freq = central_func(freqs)
        if not math.fabs(self.freq - freq) < 0.0005:
            log.error(
                "[%s] [%s] [%s] Round #%d. %s Frequency: computed f = %f, stored = %f",
                self.n,
                self.m,
                self.s,
                self.seq,
                self.central,
                freq,
                self.freq,
            )
        stddev = statistics.stdev(freqs, freq)
        if math.fabs(self.stddev - stddev) > 0.005:
            log.warn(
                "[%s] [%s] [%s] Round #%d. computed \u03c3(freq) = %f, stored \u03c3(freq) = %f. May be can be fixed.",
                self.n,
                self.m,
                self.s,
                self.seq,
                stddev,
                self.stddev,
            )
            stddev2 = statistics.stdev(freqs)
            if not math.fabs(self.stddev - stddev2) < 0.005:
                log.error(
                    "[%s] [%s] [%s] Round #%d. computed \u03c3(freq) = %f, stored \u03c3(freq) = %f",
                    self.n,
                    self.m,
                    self.s,
                    self.seq,
                    stddev2,
                    self.stddev,
                )

    def assert_no_timestamps(self):
        if not (self.begin_tstamp is None and self.end_tstamp is None):
            log.error(
                "[%s] [%s] [%s] Round #%d. Expected empty time window, got from %s to %s",
                self.n,
                self.m,
                self.s,
                self.seq,
                self.begin_tstamp,
                self.end_tstamp,
            )

    def assert_samples(self, samples):
        N = len(samples)
        if not self.nsamples == N:
            log.error(
                "[%s] [%s] [%s] Round #%d. Number of samples. Computed = %d, Stored = %d",
                self.n,
                self.m,
                self.s,
                self.seq,
                N,
                self.nsamples,
            )
        if not self.begin_tstamp == samples[0].tstamp:
            log.error(
                "[%s] [%s] [%s] Round #%d. Begin round timestamp mismatch. Round = %s, Samples[0] = %s",
                self.n,
                self.m,
                self.s,
                self.seq,
                self.begin_tstamp,
                samples[0].tstamp,
            )
        if not self.end_tstamp == samples[-1].tstamp:
            log.error(
                "[%s] [%s] [%s] Round #%d. End round timestamp mismatch. Round = %s, Samples[-1] = %s",
                self.n,
                self.m,
                self.s,
                self.seq,
                self.end_tstamp,
                samples[-1].tstamp,
            )
        for s in samples:
            if not s.role == self.role:
                log.error(
                    "[%s] [%s] [%s] Round #%d. Wrong roles Round = %s, Samples[s] = %s",
                    self.n,
                    self.m,
                    self.s,
                    self.seq,
                    self.role,
                    s.role,
                )

    async def check(self, photometer, summary):
        self.n = photometer.name
        self.m = photometer.mac
        self.s = summary.session
        log.info("[%s] [%s] [%s] Round #%d self check", self.n, self.m, self.s, self.seq)
        self.assert_round_magnitude()
        total_samples = await summary.awaitable_attrs.samples
        if self.nsamples > 0 and len(total_samples) == 0:
            self.assert_no_timestamps()
            log.info(
                "[%s] [%s] [%s] Round #%d self check ok, but 0/%d STORED SAMPLES !",
                self.n,
                self.m,
                self.s,
                self.seq,
                self.nsamples,
            )
            return
        samples = sorted(await self.awaitable_attrs.samples)
        self.assert_samples(samples)
        self.assert_freq_from_samples(samples)


class DbgSample(Sample):
    async def check(self, photometer, summary):
        n = photometer.name
        m = photometer.mac
        s = summary.session
        rounds = await self.awaitable_attrs.rounds
        rseqs = sorted([r.seq for r in rounds])
        log.info("[%s] [%s] [%s] Sample #%d in Rounds %s. self check ok", n, m, s, self.id, rseqs)


# -------------------
# Auxiliary functions
# -------------------


async def get_all_sessions(
    async_session: async_sessionmaker[AsyncSessionClass],
) -> List[datetime]:
    async with async_session() as session:
        async with session.begin():
            q = select(DbgSummary.session.distinct()).order_by(DbgSummary.role.asc())
            return (await session.scalars(q)).all()


async def check_summary(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    if meas_session is not None:
        await check_summary_single(meas_session, async_session)
    else:
        meas_session = await get_all_sessions(async_session)
        for ses in meas_session:
            await check_summary_single(ses, async_session)


async def check_rounds(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    if meas_session is not None:
        await check_rounds_single(meas_session, async_session)
    else:
        meas_session = await get_all_sessions(async_session)
        for ses in meas_session:
            await check_rounds_single(ses, async_session)


async def check_samples(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    if meas_session is not None:
        await check_samples_single(meas_session, async_session)
    else:
        meas_session = await get_all_sessions(async_session)
        for ses in meas_session:
            await check_samples_single(ses, async_session)


async def check_all(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    if meas_session is not None:
        await check_all_single(meas_session, async_session)
    else:
        meas_session = await get_all_sessions(async_session)
        for ses in meas_session:
            await check_all_single(ses, async_session)


async def check_summary_single(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    async with async_session() as session:
        async with session.begin():
            q = (
                select(DbgPhotometer, DbgSummary)
                .join(DbgSummary)
                .where(DbgSummary.session == meas_session)
                .order_by(DbgSummary.role.asc())
            )
            result = (await session.execute(q)).all()
            for row in result:
                photometer = row[0]
                summary = row[1]
                await summary.check(photometer)


async def check_rounds_single(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    async with async_session() as session:
        async with session.begin():
            q = (
                select(DbgPhotometer, DbgSummary, DbgRound)
                .join(DbgSummary, DbgPhotometer.id == DbgSummary.phot_id)
                .join(DbgRound, DbgSummary.id == DbgRound.summ_id)
                .filter(DbgSummary.session == meas_session)
                .order_by(DbgSummary.role.asc())
            )
            result = (await session.execute(q)).all()
            for row in result:
                photometer = row[0]
                summary = row[-2]
                round_ = row[-1]
                await round_.check(photometer, summary)


async def check_samples_single(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    async with async_session() as session:
        async with session.begin():
            q = (
                select(DbgPhotometer, DbgSummary, DbgSample)
                .join(DbgSummary, DbgPhotometer.id == DbgSummary.phot_id)
                .join(DbgSample, DbgSummary.id == DbgSample.summ_id)
                .filter(DbgSummary.session == meas_session)
                .order_by(DbgSummary.role.asc())
            )
            result = (await session.execute(q)).all()
            for row in result:
                photometer = row[0]
                summary = row[-2]
                sample = row[-1]
                await sample.check(photometer, summary)


async def check_all_single(
    meas_session: datetime, async_session: async_sessionmaker[AsyncSessionClass]
) -> None:
    await check_summary_single(meas_session, async_session)
    await check_rounds_single(meas_session, async_session)
    await check_samples_single(meas_session, async_session)


# --------------
# main functions
# --------------

TABLE = {
    "summary": check_summary,
    "rounds": check_rounds,
    "samples": check_samples,
}


async def qa(args) -> None:
    async with engine.begin():
        if args.command != "all":
            func = TABLE[args.command]
            meas_session = args.session
            await func(meas_session, AsyncSession)
        else:
            for name in ("summary", "rounds", "samples"):
                meas_session = args.session
                func = TABLE[name]
                await func(meas_session, AsyncSession)
    await engine.dispose()


def add_args(parser):
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("summary", parents=[prs_session()], help="Browse summary data")
    subparser.add_parser("rounds", parents=[prs_session()], help="Browse rounds data")
    subparser.add_parser("samples", parents=[prs_session()], help="Browse samples data")
    subparser.add_parser("all", parents=[prs_session()], help="Browse all data")


def prs_session() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-s",
        "--session",
        metavar="<YYYY-MM-DDTHH:MM:SS>",
        type=vdate,
        default=None,
        help="Session date",
    )
    return parser


async def cli_main(args: Namespace) -> None:
    sqa_logging(args)
    await qa(args)


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
