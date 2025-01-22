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

from argparse import ArgumentParser, Namespace
from typing import Sequence, Iterable
from sqlite3 import Connection

# -------------------
# Third party imports
# -------------------

from lica.cli import execute
from lica.sqlite import open_database

# --------------
# local imports
# -------------

from ... import __version__
from ..util import parser as prs

# ----------------
# Module constants
# ----------------

DESCRIPTION = "TESS-W Calibration Database data extraction tool"

CONFIG_H = ("section", "prop", "value")
BATCH_H = ("begin_tstamp", "end_tstamp", "email_sent", "calibrations", "comment")
PHOTOMETER_H = ("name", "mac", "sensor", "model", "firmware", "filter", "plug", "box", "collector")
SUMMARY_H = (
    "name",
    "mac",
    "session",
    "role",
    "calibration",
    "calversion",
    "author",
    "nrounds",
    "zp_offset",
    "upd_flag",
    "prev_zp",
    "zero_point",
    "zero_point_method",
    "freq",
    "freq_method",
    "mag",
    "comment",
)
ROUNDS_H = (
    "session",
    "round",
    "role",
    "begin_tstamp",
    "end_tstamp",
    "central",
    "freq",
    "stddev",
    "mag",
    "zp_fict",
    "zero_point",
    "nsamples",
    "duration",
)
SAMPLES_H = ("session", "tstamp", "role", "seq", "freq", "temp_box")

# -----------------------
# Module global variables
# -----------------------

# get the root logger
log = logging.getLogger(__name__.split(".")[-1])

# -------------------
# Auxiliary functions
# -------------------


def write_csv(path: str, header: Sequence[str], iterable: Iterable[str], delimiter: str = ";"):
    with open(path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=delimiter)
        writer.writerow(header)
        for row in iterable:
            writer.writerow(row)
    log.info("Written to %s", path)


def _extract_batch(path: str, conn: Connection) -> None:
    log.info("Extracting from batch_t table.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT begin_tstamp, end_tstamp, calibrations, email_sent, comment 
        FROM batch_t 
        ORDER BY begin_tstamp
    """)
    write_csv(path, BATCH_H, cursor)


def _extract_config(path: str, conn: Connection) -> None:
    log.info("Extracting from config_t table.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT section, property AS prop, value
        FROM config_t 
        ORDER BY section, prop
    """)
    write_csv(path, CONFIG_H, cursor)


def _extract_photometer(path: str, conn: Connection) -> None:
    log.info("Extracting from summary_t table for photometer data.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT name,mac,sensor,model,firmware,filter,plug,box,collector,comment
        FROM summary_t
        WHERE comment IS NULL
        ORDER BY name
    """)
    rows1 = cursor.fetchall()
    cursor.execute("""
        SELECT DISTINCT name,mac,sensor,model,firmware,filter,plug,box,collector,SUBSTR(comment,7)
        FROM summary_t
        WHERE comment LIKE 'Phot: %'
        ORDER BY name
    """)
    rows2 = cursor.fetchall()
    cursor.execute("""
        SELECT DISTINCT name,mac,sensor,model,firmware,filter,plug,box,collector,SUBSTR(comment,11)
        FROM summary_t
        WHERE comment LIKE 'PhotSumm: %'
        ORDER BY name
    """)
    rows3 = cursor.fetchall()
    write_csv(path, PHOTOMETER_H, rows1 + rows2 + rows3)


def _extract_summary(path: str, conn: Connection) -> None:
    log.info("Extracting from summary_t table for summary calibration data.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT name,mac,session,role,calibration,calversion,author,nrounds,offset AS zp_offset,
            upd_flag,prev_zp,zero_point,zero_point_method,freq,freq_method,mag,comment
        FROM summary_t
        WHERE comment IS NULL
        ORDER BY name
    """)
    rows1 = cursor.fetchall()
    cursor.execute("""
        SELECT DISTINCT name,mac,session,role,calibration,calversion,author,nrounds,offset AS zp_offset,
            upd_flag,prev_zp,zero_point,zero_point_method,freq,freq_method,mag, SUBSTR(comment,7)
        FROM summary_t
        WHERE comment LIKE 'Summ: %'
        ORDER BY name
    """)
    rows2 = cursor.fetchall()
    cursor.execute("""
        SELECT DISTINCT name,mac,session,role,calibration,calversion,author,nrounds,offset AS zp_offset,
            upd_flag,prev_zp,zero_point,zero_point_method,freq,freq_method,mag,SUBSTR(comment,11)
        FROM summary_t
        WHERE comment LIKE 'PhotSumm: %'
        ORDER BY name
    """)
    rows3 = cursor.fetchall()
    write_csv(path, SUMMARY_H, rows1 + rows2 + rows3)


def _extract_rounds(path: str, conn: Connection) -> None:
    log.info("Extracting from rounds_t table.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT session,round,role,begin_tstamp,end_tstamp,central,freq,stddev,mag,zp_fict,zero_point,nsamples,duration
        FROM rounds_t
        ORDER BY session, round, role
    """)
    write_csv(path, ROUNDS_H, cursor)


def _extract_samples(path: str, conn: Connection) -> None:
    log.info("Extracting from samples_t table.")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session,tstamp,role,seq,freq,temp_box 
        FROM samples_t 
        ORDER BY session, tstamp, role 
    """)
    write_csv(path, SAMPLES_H, cursor)


# --------------
# main functions
# --------------


def add_args(parser: ArgumentParser) -> None:
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("config", parents=[prs.odir()], help="Extract config CSV")
    subparser.add_parser("batch", parents=[prs.odir()], help="Extract batch CSV")
    subparser.add_parser("photometer", parents=[prs.odir()], help="Extract photometer CSV")
    subparser.add_parser("summary", parents=[prs.odir()], help="Extract summary CSV")
    subparser.add_parser("rounds", parents=[prs.odir()], help="Extract rounds CSV")
    subparser.add_parser("samples", parents=[prs.odir()], help="Extract samples CSV")
    subparser.add_parser("all", parents=[prs.odir()], help="Extract all CSVs")


TABLE = {
    "config": _extract_config,
    "batch": _extract_batch,
    "photometer": _extract_photometer,
    "summary": _extract_summary,
    "rounds": _extract_rounds,
    "samples": _extract_samples,
}


def cli_main(args: Namespace) -> None:
    connection, _ = open_database(env_var="SOURCE_DATABASE")
    if args.command not in ("all",):
        func = TABLE[args.command]
        path = os.path.join(args.output_dir, args.command + ".csv")
        func(path, connection)
        log.info("done.")
    else:
        for name in ("config", "batch", "photometer", "summary", "rounds", "samples"):
            path = os.path.join(args.output_dir, name + ".csv")
            func = TABLE[name]
            func(path, connection)
    connection.close()


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
