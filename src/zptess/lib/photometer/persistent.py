# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------
from __future__ import annotations

import logging
import asyncio
from collections import defaultdict

from typing import Any, Mapping, Dict, List


# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from pubsub import pub
from lica.asyncio.photometer import Role
from lica.sqlalchemy.asyncio.dbase import AsyncSession
# --------------
# local imports
# -------------

from .volatile import Controller as VolatileCalibrator
from .types import Event
from ..dbase.model import Photometer, Summary, Round, Sample
from .. import Calibration
from ... import __version__

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# -------------------
# Auxiliary functions
# -------------------

# -----------------
# Auxiliary classes
# -----------------

class Controller(VolatileCalibrator):
    """
    Database-based Photometer Calibration Controller
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
        common_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params, common_params)
        self.db_queue = asyncio.Queue()

    async def init(self) -> None:
        await super().init()
        self.db_task = asyncio.create_task(self.db_writer())

    async def calibrate(self) -> float:
        zp = await super().calibrate()
        asyncio.gather(self.db_task)
        return zp

    async def db_writer(self) -> None:
        self.db_active = True
        self.temp_round_info = list()
        self.temp_round_samples = list()
        while self.db_active:
            msg = await self.db_queue.get()
            event = msg["event"]
            if event == Event.CAL_START:
                pass
            elif event == Event.ROUND:
                self.temp_round_info.append(msg["info"])
            elif event == Event.SUMMARY:
                self.temp_summary = msg["info"]
            else:
                await self.do_persist()
        log.info("Database listener ends here")

    def on_calib_start(self) -> None:
        pub.sendMessage(Event.CAL_START)
        msg = {"event": Event.CAL_START, "info": None}
        self.db_queue.put_nowait(msg)

    def on_calib_end(self) -> None:
        pub.sendMessage(Event.CAL_END)
        msg = {"event": Event.CAL_END, "info": None}
        self.db_queue.put_nowait(msg)

    def on_round(self, round_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.ROUND, **round_info)
        # We must copy the sequence of samples of a given round
        # since the background filling tasks are active
        msg = {
            "event": Event.ROUND,
            "info": round_info,
        }
        self.db_queue.put_nowait(msg)

    def on_summary(self, summary_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.SUMMARY, **summary_info)
        msg = {"event": Event.SUMMARY, "info": summary_info}
        self.db_queue.put_nowait(msg)

    async def do_photometer(self, session: AsyncSession) -> Dict[Role, Photometer]:
        phot = dict()
        for role in self.roles:
            name = self.phot_info[role]["name"]
            mac = self.phot_info[role]["mac"]
            q = select(Photometer).where(Photometer.mac == mac, Photometer.name == name)
            phot[role] = (await session.scalars(q)).one_or_none()
            if phot[role] is None:
                col = dict()
                for key in ("name", "mac", "model", "sensor", "freq_offset", "firmware"):
                    col[key] = self.phot_info[role][key] or None
                col["freq_offset"] = col["freq_offset"] or 0.0
                log.info("Creating %s DB Photometer with data %s", role, col)
                phot[role] = Photometer(**col)
                session.add(phot[role])
        return phot

    def do_summary(
        self, session: AsyncSession, photometers: Dict[Role, Photometer]
    ) -> Dict[Role, Summary]:
        log.info("A por los sumarios")
        summary = dict()
        for role, phot in photometers.items():
            summary[role] = Summary(
                session=self.meas_session,
                role=role,
                calibration=Calibration.AUTO,
                calversion=__version__,
                author=self.author,
                zp_offset=self.zp_offset if role == Role.TEST else 0,
                prev_zp=self.phot_info[role]["zp"] if role == Role.TEST else self.zp_abs,
                zero_point=self.temp_summary["best_zero_point"]
                if role == Role.TEST
                else self.zp_abs,
                zero_point_method=self.temp_summary["best_zero_point_method"]
                if role == Role.TEST
                else None,
                freq=self.temp_summary["best_freq"][role],
                freq_method=self.temp_summary["best_freq_method"][role],
                mag=self.temp_summary["best_mag"][role],
                nrounds=self.nrounds,
            )
            summary[role].photometer = phot
            session.add(summary[role])
        return summary

    def do_rounds(
        self, session: AsyncSession, summaries: Dict[Role, Photometer]
    ) -> Dict[Role, List[Round]]:
        log.info("A por los rounds")
        rounds = defaultdict(list)
        for i, round_info in enumerate(self.temp_round_info):
            for role, summary in summaries.items():
                samples = self.accum_samples[role][i]
                r = Round(
                    seq=round_info["current"],
                    role=role,
                    freq=round_info["stats"][role][0],
                    stddev=round_info["stats"][role][1],
                    mag=round_info["stats"][role][2],
                    central=self.central,
                    zp_fict=self.zp_fict,
                    zero_point=round_info["zero_point"] if role == Role.TEST else None,
                    nsamples=len(samples),
                    begin_tstamp=samples[0]["tstamp"],
                    end_tstamp=samples[-1]["tstamp"],
                    duration=(samples[-1]["tstamp"] - samples[0]["tstamp"]).total_seconds(),
                    summary=summary,
                )
                rounds[role].append(r)
                log.info(r)
                session.add(r)
        return rounds

    def do_samples(
        self, session: AsyncSession, summaries: Dict[Role, Summary]
    ) -> Dict[Role, List[Sample]]:
        log.info("A por los samples")
        samples_db = dict()
        for role, summary in summaries.items():
            # samples = set(item for item in q for q in self.accum_samples[role])
            samples = set()
            for q in self.accum_samples[role]:
                samples.update(set(q))
            samples_db[role] = [
                Sample(
                    tstamp=sample["tstamp"],
                    role=role,
                    seq=sample["seq"],
                    freq=sample["freq"],
                    temp_box=sample["tamb"],
                    summary=summary,
                )
                for sample in samples
            ]
            for s in samples_db[role]:
                log.info(s)
                session.add(s)
        return samples_db

    def do_samples_to_rounds(
        self,
        session: AsyncSession,
        rounds: Dict[Role, List[Round]],
        samples: Dict[Role, List[Sample]],
    ) -> None:
        pass

    async def do_persist(self):
        async with self.Session() as session:
            async with session.begin():
                photometer = await self.do_photometer(session)
                log.info(photometer)
                summary = self.do_summary(session, photometer)
                log.info(summary)
                rounds = self.do_rounds(session, summary)
                samples = self.do_samples(session, summary)
                self.do_samples_to_rounds(session, rounds, samples)

        self.db_active = False
