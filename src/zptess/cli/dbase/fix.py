# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------


import math
import logging
from argparse import ArgumentParser, Namespace
from datetime import datetime
import statistics

# -------------------
# Third party imports
# -------------------

from lica.validators import vdate


from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass
from sqlalchemy.ext.asyncio import async_sessionmaker

from lica.sqlalchemy import sqa_logging
from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.cli import execute



#--------------
# local imports
# -------------

from ...lib.dbase.model import Round
from ... import __version__
from ...lib import CentralTendency

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Calibration Database fix stuff tool"

# -----------------------
# Module global variables
# -----------------------

log = logging.getLogger(__name__.split('.')[-1])

# -------------------
# Auxiliary functions
# -------------------


def central(method: str):
    assert method in CentralTendency, f"Statistics central method {method} is not supported"
    f = statistics.mode
    if method == CentralTendency.MEAN.value:
        f = statistics.mean
    elif method == CentralTendency.MEDIAN.value:
        f = statistics.median
    return f


def rounds(conn, session, role):
    params = {'session': session, 'role': role}
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT begin_tstamp, end_tstamp, round, freq, central, stddev
        FROM rounds_t
        WHERE session = :session AND role = :role
        AND begin_tstamp IS NOT NULL AND end_tstamp IS NOT NULL
    ''', params)
    return cursor


def samples(conn, session, begin_tstamp, end_tstamp, role):
    params = {'session': session, 'role': role, 'begin_tstamp': begin_tstamp, 'end_tstamp': end_tstamp}
    cursor = conn.cursor()
    cursor.execute('''
        SELECT freq FROM samples_t
        WHERE session = :session AND role = :role
        AND tstamp BETWEEN :begin_tstamp AND :end_tstamp
        ORDER BY tstamp
    ''', params)
    return list(result[0] for result in cursor)


def fix_stddev(conn, new_stddev, old_stddev, name, mac, session, role, seq):
    params = {'session': session, 'role': role, 'seq': seq, 'new_stddev': new_stddev, 'old_stddev': old_stddev}
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE rounds_t
            SET stddev = :new_stddev       
            WHERE session = :session AND role = :role AND round = :seq
            AND stddev = :old_stddev
        ''', params)
        log.info("[%s] [%s] [%s] Round #%d update old %f => new %f", name, mac, session, seq, old_stddev, new_stddev)


def compare_and_fix_stddev(conn, dry_run, name, mac, session, role, seq, freq, freqs, freq_method, stddev):
    central_func = central(freq_method)
    computed_freq = central_func(freqs)
    computed_stddev = statistics.stdev(freqs, computed_freq)
    if not math.fabs(computed_stddev - stddev) < 0.005:
        log.warn("[%s] [%s] [%s] Round #%d computed \u03C3(%s %f)=%f, != stored \u03C3(%f)=%f", 
            name, mac, session, seq, freq_method, computed_freq, computed_stddev, freq, stddev,)
        freq2 = statistics.mean(freqs)
        computed2_stddev = statistics.stdev(freqs, freq2)
        if not math.fabs(computed2_stddev - stddev) < 0.005:
            log.error( "[%s] [%s] [%s] Round #%d Computed \u03C3(%s %f)=%f != stored\u03C3(%f) %f",
                name, mac, session, seq, 'mean', freq2, computed2_stddev, freq, stddev)
        elif not dry_run:
            fix_stddev(conn, computed_stddev, stddev, name, mac, session, role, seq)


def fix_rounds_stddev(conn, dry_run, name, mac, session, role) -> None:
    for begin_tstamp, end_tstsamp, seq, freq, central, stddev in rounds(conn, session, role):
        freqs = samples(conn, session, begin_tstamp, end_tstsamp, role)
        compare_and_fix_stddev(conn, dry_run, name, mac, session, role, seq, freq, freqs, central, stddev)

    
def sessions(conn, session=None):   
    cursor = conn.cursor()
    if session:
        params = {'session': session}
        sql = 'SELECT name, mac, session, role FROM summary_t WHERE session = :session ORDER BY session ASC'
    else:
        params = {}
        sql = 'SELECT name, mac, session, role FROM summary_t ORDER BY session ASC'
    cursor.execute(sql, params)
    return cursor


async def fix_fict_zp(async_session: async_sessionmaker[AsyncSessionClass], meas_session: datetime, dry_run: bool, default_zp = 20.50) -> None:
    log.info("Fixing Ficticious ZP to %s", default_zp)
    stmt = update(Round).where(Round.zp_fict != default_zp).values(zp_fict = default_zp)
    if not dry_run:
        async with async_session() as session:
            async with session.begin():
                await session.execute(stmt)

# --------------
# main functions
# --------------


def add_args(parser: ArgumentParser):
    subparser = parser.add_subparsers(dest='command')
    parser_rounds = subparser.add_parser('rounds', help='Fix rounds stuff')
    roex = parser_rounds.add_mutually_exclusive_group(required=True)
    roex.add_argument('-t','--stddev',  action='store_true',  help='Fix rounds stddev')
    roex.add_argument('-z','--zp-fict',  action='store_true',  help='Fix Ficticious ZP to 20.50')
    parser_rounds.add_argument('-s', '--session', type=vdate, default=None, help='Session date')
    parser_rounds.add_argument('-d', '--dry-run', action='store_true', help='Do not update database')
    

async def fix(args: Namespace) -> None:
    async with engine.begin():
        if args.stddev:
            await fix_rounds_stddev(AsyncSession, args.session)
        elif args.zp_fict:
            await fix_fict_zp(AsyncSession, args.session, args.dry_run)
    await engine.dispose()


async def cli_main(args: Namespace) -> None:
    sqa_logging(args)
    await fix(args)


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
