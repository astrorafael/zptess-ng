# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
import asyncio

from typing import Mapping, Dict, Iterable

# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass
from sqlalchemy.ext.asyncio import async_sessionmaker

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .ring import RingBuffer
from ..lib.dbase.model import Config

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


class Reader:
    """
    Reader Controller specialized in reading the photometers
    with or without ring buffer
    """

    def __init__(
        self,
        which: Iterable[str],
        models: Mapping[Role, PhotModel] | None,
        sensors: Mapping[Role, Sensor] | None,
        endpoint: Mapping[Role, str] | None,
        old_proto: Mapping[Role, bool] | None,
        buffered: bool = False,
    ):
        self.Session = AsyncSession
        self.photometer = [None, None]
        self.producer = [None, None]
        self.consumer = [None, None]
        self.ring = [None, None]
        self.cur_mac = [None, None]
        self.which = which
        self.sensor = [None, None]
        self.model = [None, None]
        self.role = [None, None]
        self.old_proto = [None, None]
        self.endpoint = [None, None]
        self.buffered = buffered
        if "ref" in self.which:
            self.sensor[Role.REF] = sensors[Role.REF]
            self.model[Role.REF] = models[Role.REF]
            self.old_proto[Role.REF] = old_proto[Role.REF]
            self.endpoint[Role.REF] =  endpoint[Role.REF]
            self.role[Role.REF] = Role.REF
        if "test" in self.which:
            self.sensor[Role.TEST] = sensors[Role.TEST]
            self.model[Role.TEST] = models[Role.TEST]
            self.old_proto[Role.TEST] = old_proto[Role.TEST]
            self.endpoint[Role.TEST] =  endpoint[Role.TEST]
            self.role[Role.TEST] = Role.TEST

    async def _load(self, session, section: str, prop: str) -> str | None:
        async with session:
            q = select(Config.value).where(
                        Config.section == section, Config.prop == prop
                    )
            return (await session.scalars(q)).one_or_none()

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s (buffered=%s)",
            self.__class__.__name__,
            self.which,
            self.buffered,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        async with self.Session() as session:
            if "ref" in self.which:
                v = await self._load(session, "ref-device", "model")
                self.model[Role.REF] = self.model[Role.REF] or v
                v = await self._load(session, "ref-device", "sensor")
                self.sensor[Role.REF] = self.sensor[Role.REF] or v
                v = await self._load(session, "ref-device", "old-proto")
                self.old_proto[Role.REF] = self.old_proto[Role.REF] or v
                v = await self._load(session, "ref-device", "endpoint")
                self.endpoint[Role.REF] = self.endpoint[Role.REF] or v
                self.photometer[Role.REF] = builder.build(self.model[Role.REF], Role.REF)
                if self.buffered:
                    ring_buffer_size = int(await self._load(session, "ref-stats", "samples"))
                    self.ring[Role.REF] = RingBuffer(ring_buffer_size)
            if "test" in self.which:
                v = await self._load(session, "test-device", "model")
                self.model[Role.TEST] = self.model[Role.TEST] or v
                v = await self._load(session, "test-device", "sensor")
                self.sensor[Role.TEST] = self.sensor[Role.TEST] or v
                v = await self._load(session, "test-device", "old-proto")
                self.old_proto[Role.TEST] = self.old_proto[Role.TEST] or v
                v = await self._load(session, "test-device", "endpoint")
                self.endpoint[Role.TEST] = self.endpoint[Role.TEST] or v
                self.photometer[Role.TEST] = builder.build(self.model[Role.TEST], Role.TEST)
                if self.buffered:
                    ring_buffer_size = int(await self._load(session, "test-stats", "samples"))
                    self.ring[Role.TEST] = RingBuffer(ring_buffer_size)

    async def info(self, role: Role) -> Dict[str, str]:
        log = logging.getLogger(role.tag())
        try:
            phot_info = await self.photometer[role].get_info()
        except asyncio.exceptions.TimeoutError:
            txt = f"Failed contacting {role.tag()} photometer"
            log.error(txt)
            return {"error_messg": txt}
        except Exception as e:
            log.error(e)
            txt = f"{e}"
            return {"err_msg": txt}
        else:
            phot_info["endpoint"] = role.endpoint()
            return phot_info

    async def receive(self, role: Role):
        while True:
            log.info("cucu")
            msg = await self.photometer[role].queue.get()
            if self.buffered:
                self.ring[role].append(msg)
            log.info("tras")
            line = f"{msg['tstamp'].strftime('%Y-%m-%d %H:%M:%S')} [{msg.get('seq')}] f={msg['freq']} Hz, tbox={msg['tamb']}, tsky={msg['tsky']}"
            freqs = self.ring[role].frequencies()
            progress = 1
            yield line, freqs, progress
