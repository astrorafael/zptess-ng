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
import glob
import zipfile
import logging
import itertools

import ssl
import smtplib

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


from datetime import datetime
from typing import Sequence, Tuple, Any

# -------------------
# Third party imports
# -------------------

import aiohttp

from lica.sqlalchemy.asyncio.dbase import AsyncSession

# --------------
# local imports
# -------------

from ..dbase.model import SummaryView, RoundView, SampleView, Config, Batch
from sqlalchemy import select, func, cast, Integer


SUMMARY_EXPORT_HEADERS = (
    "Model",
    "Name",
    "MAC",
    "Firmware",
    "Sensor",
    "Calibration Date (UTC)",
    "Calibration",
    "Cal. SW. Version",
    "Ref. Mag.",
    "Ref. Freq.",
    "Test Mag.",
    "test freq.",
    "Ref-Test Mag. Diff.",
    "Raw ZP",
    "ZP Offset",
    "Final ZP",
    "Prev. ZP",
    "Filter",
    "Plug",
    "Box",
    "Collector",
    "Author",
    "Comment",
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


# -------------------
# Auxiliary functions
# -------------------


# Adapted From https://realpython.com/python-send-email/
def email_send(
    subject: str,
    body: str,
    sender: str,
    receivers: str,
    attachment: str,
    host: str,
    port: str,
    password: str,
    confidential: bool = False,
):
    msg_receivers = receivers
    receivers = receivers.split(sep=",")
    message = MIMEMultipart()
    message["Subject"] = subject
    # Create a multipart message and set headers
    if confidential:
        message["From"] = sender
        message["To"] = sender
        message["Bcc"] = msg_receivers
    else:
        message["From"] = sender
        message["To"] = msg_receivers

    # Add body to email
    message.attach(MIMEText(body, "plain"))

    # Open file in binary mode
    with open(attachment, "rb") as fd:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(fd.read())

    # Encode file in ASCII characters to send by email
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {os.path.basename(attachment)}",
    )
    # Add attachment to message and convert message to string
    message.attach(part)
    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(sender, password)
        server.sendmail(sender, receivers, message.as_string())


# -----------------
# Auxiliary classes
# -----------------


class Controller:
    def __init__(
        self,
        base_dir: str,
        filename_prefix: str,
        begin_tstamp: datetime = None,
        end_tstamp: datetime = None,
    ):
        self.begin_tstamp = begin_tstamp
        self.end_tstamp = end_tstamp
        self.base_dir = base_dir if os.path.isabs(base_dir) else os.path.abspath(base_dir)
        self.filename_prefix = filename_prefix

    # ----------
    # Public API
    # ----------

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
                        SummaryView.session.between(t0, t1),
                        SummaryView.upd_flag == True,  # noqa: E712
                    ).order_by(cast(func.substr(SummaryView.name, 6), Integer), SummaryView.session)
                else:
                    q = q.where(
                        SummaryView.name.like("stars%"),
                        SummaryView.upd_flag == True,  # noqa: E712
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

    def export_summaries(self, summaries: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"summary_{self.filename_prefix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(SUMMARY_EXPORT_HEADERS)
            for summary in summaries:
                csv_writer.writerow(summary)

    def export_rounds(self, rounds: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"rounds_{self.filename_prefix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(ROUND_EXPORT_HEADERS)
            for round_ in rounds:
                csv_writer.writerow(round_)

    def export_samples(self, samples: Sequence[Tuple[Any]]) -> None:
        csv_path = os.path.join(self.base_dir, f"samples_{self.filename_prefix}.csv")
        log.info("exporting %s", os.path.basename(csv_path))
        with open(csv_path, "w") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=";")
            csv_writer.writerow(SAMPLE_EXPORT_HEADERS)
            for sample in samples:
                csv_writer.writerow(sample)

    def pack(self) -> str:
        """Pack all files in the ZIP file given by options"""
        parent_dir = os.path.dirname(self.base_dir)
        zip_file = os.path.join(parent_dir, self.filename_prefix + ".zip")
        log.info("Creating ZIP File: '%s'", zip_file)
        file_paths = [
            os.path.join(os.path.basename(self.base_dir), fname)
            for fname in glob.glob("*.csv", root_dir=self.base_dir)
        ]
        with zipfile.ZipFile(zip_file, "w") as myzip:
            for myfile in file_paths:
                myzip.write(myfile)
        return zip_file

    async def check_internet(self) -> bool:
        result = True
        timeout = aiohttp.ClientTimeout(total=5)  # 5 seconds timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get("http://www.google.com") as response:
                    status = response.status
                    log.info("Connected to Internet. Status code: %s", status)
            except Exception as e:
                log.exception(e)
                result = False
        return result

    async def load_email_config(self) -> None:
        # Read email configuration
        smtp_keys = set(("host", "port", "sender", "password", "receivers"))
        async with AsyncSession() as session:
            async with session.begin():
                q = select(Config).where(Config.section == "smtp").order_by(Config.prop)
                configs = (await session.scalars(q)).all()
        properties = set(cfg.prop for cfg in configs)
        if properties != smtp_keys:
            missing = smtp_keys - properties
            raise Exception("Missing properies in the database: %s", missing)
        self.mail_cfg = dict(map(lambda cfg: (cfg.prop, cfg.value), configs))
        self.mail_cfg["port"] = int(self.mail_cfg["port"])

    def send_email(self, zip_file_path: str) -> bool:
        try:
            email_sent = True
            email_send(
                subject=f"[STARS4ALL] TESS calibration data from {self.begin_tstamp} to {self.end_tstamp}",
                body="Find attached hereafter the summary, rounds and samples from this calibration batch",
                sender=self.mail_cfg["sender"],
                receivers=self.mail_cfg["receivers"],
                attachment=zip_file_path,
                host=self.mail_cfg["host"],
                port=self.mail_cfg["port"],
                password=self.mail_cfg["password"],
            )
        except Exception as e:
            email_sent = False
            log.exception(e)
        return email_sent

    async def update_batch(self, batch: Batch, email_sent: bool) -> None:
        async with AsyncSession() as session:
            async with session.begin():
                batch.email_sent = email_sent
                session.add(batch)

    # ---------------
    # Private methods
    # ---------------

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
