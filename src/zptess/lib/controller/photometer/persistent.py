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
from ...dbase.model import Photometer, Summary, Round, Sample
from ... import Calibration
from .... import __version__

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

    # ==========
    # Public API
    # ==========

    async def init(self) -> None:
        await super().init()
        self.db_task = asyncio.create_task(self.db_writer_task())

    async def calibrate(self) -> float:
        zp = await super().calibrate()
        await asyncio.wait([self.db_task])
        return zp

    async def write_zp(self, zero_point: float) -> float:
        """May raise asyncio.exceptions.TimeoutError in particular"""
        try:
            stored_zero_point = await super().write_zp(zero_point)
        except Exception:
            updated = False
        else:
            updated = True
        async with self.Session() as session:
            async with session.begin():
                q = select(Summary).where(Summary.session == self.meas_session)
                db_summaries = (await session.scalars(q)).all()
                for db_summary in db_summaries:
                    db_summary.upd_flag = False if db_summary.role == Role.REF else updated
                    if not updated:
                        db_summary.comment = f"{self.phot_info[Role.TEST]['name']} not updated because of HTTP Timeout"
        return stored_zero_point

    async def not_updated(self, zero_point: float, msg: str):
        """What to do when the Zero Point is not updated by the client code"""
        async with self.Session() as session:
            async with session.begin():
                q = select(Summary).where(Summary.session == self.meas_session)
                db_summaries = (await session.scalars(q)).all()
                for db_summary in db_summaries:
                    db_summary.upd_flag = False
                    db_summary.comment = msg

    # ===========
    # Private API
    # ===========

    # --------------------
    # Hooks implementation
    # --------------------

    def _on_calib_start(self) -> None:
        pub.sendMessage(Event.CAL_START)
        msg = {"event": Event.CAL_START, "info": None}
        self.db_queue.put_nowait(msg)

    def _on_calib_end(self) -> None:
        pub.sendMessage(Event.CAL_END)
        msg = {"event": Event.CAL_END, "info": None}
        self.db_queue.put_nowait(msg)

    def _on_round(self, round_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.ROUND, **round_info)
        # We must copy the sequence of samples of a given round
        # since the background filling tasks are active
        msg = {
            "event": Event.ROUND,
            "info": round_info,
        }
        self.db_queue.put_nowait(msg)

    def _on_summary(self, summary_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.SUMMARY, **summary_info)
        msg = {"event": Event.SUMMARY, "info": summary_info}
        self.db_queue.put_nowait(msg)

    # ----------------------------------
    # Coroutines to be turned into Tasks
    # ----------------------------------

    async def db_writer_task(self) -> None:
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
                await self._save_all()

    # ----------------------
    # Private helper methods
    # ----------------------

    async def _save_photometers(self, session: AsyncSession) -> Dict[Role, Photometer]:
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
                phot[role] = Photometer(**col)
                session.add(phot[role])
        return phot

    def _save_summaries(
        self, session: AsyncSession, photometers: Dict[Role, Photometer]
    ) -> Dict[Role, Summary]:
        db_summary = dict()
        for role, phot in photometers.items():
            db_summary[role] = Summary(
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
                photometer=phot,  # This is really a 1:N relationship
            )
            session.add(db_summary[role])
        return db_summary

    def _save_rounds(
        self, session: AsyncSession, db_summaries: Dict[Role, Summary]
    ) -> Dict[Role, List[Round]]:
        db_rounds = defaultdict(list)
        for i, round_info in enumerate(self.temp_round_info):
            for role, summary in db_summaries.items():
                samples = self.accum_samples[role][i]
                tstamps = self.time_intervals[role][i]
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
                    begin_tstamp=tstamps[0],
                    end_tstamp=tstamps[1],
                    duration=(tstamps[1] - tstamps[0]).total_seconds(),
                    summary=summary,  # This is really a 1:N relationship
                )
                db_rounds[role].append(r)
                log.debug(r)
                session.add(r)
        return db_rounds

    def _save_samples(
        self,
        session: AsyncSession,
        db_summaries: Dict[Role, Summary],
        db_rounds: Dict[Role, List[Round]],
    ) -> Dict[Role, List[Sample]]:
        db_samples = dict()
        samples = defaultdict(set)
        # This double loop accumulate unique samples
        # dispersed in the rounds
        for role, summary in db_summaries.items():
            for q in self.accum_samples[role]:
                samples[role].update(q)
            db_samples[role] = [
                Sample(
                    tstamp=sample["tstamp"],
                    role=role,
                    seq=sample["seq"],
                    freq=sample["freq"],
                    temp_box=sample["tamb"],
                    summary=summary,
                )
                for sample in samples[role]
            ]
            # Adding the database sample objects to the summary
            for s in db_samples[role]:
                log.debug(s)
                session.add(s)
        # Now assign the samples to the corresponding round
        # The final list of unique samples is tested against the list of round samples
        # and added to the database round object if so.
        # A bit tricky (3-level for loop)
        for role in self.roles:
            for sample, db_sample in zip(samples[role], db_samples[role]):
                for i, db_round in enumerate(db_rounds[role]):
                    if sample in self.accum_samples[role][i]:
                        db_round.samples.append(db_sample)
        return db_samples

    async def _save_all(self):
        async with self.Session() as session:
            async with session.begin():
                db_photometers = await self._save_photometers(session)
                log.info("Saving %d photometer entries", len(db_photometers))
                log.debug(db_photometers)
                db_summaries = self._save_summaries(session, db_photometers)
                log.info("Saving %d summary entries", len(db_summaries))
                log.debug(db_summaries)
                db_rounds = self._save_rounds(session, db_summaries)
                log.info("Saving %d %s round entries", len(db_rounds[Role.REF]), Role.REF)
                log.info("Saving %d %s round entries", len(db_rounds[Role.TEST]), Role.TEST)
                db_samples = self._save_samples(session, db_summaries, db_rounds)
                log.info("Saving %d %s sample entries", len(db_samples[Role.REF]), Role.REF)
                log.info("Saving %d %s sample entries", len(db_samples[Role.TEST]), Role.TEST)
        self.db_active = False
