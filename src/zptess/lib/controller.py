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

SECTION = {Role.REF: "ref-device", Role.TEST: "test-device"}
SECTION2 = {Role.REF: "ref-stats", Role.TEST: "teststats"}

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
        log_msg: Mapping[Role, bool] | None,
        buffered: bool = False,
    ):
        self.Session = AsyncSession
        self.photometer = dict()
        self.producer = dict()
        self.consumer = dict()
        self.ring = dict()
        self.cur_mac = dict()

        self.which = which
        self.sensor = sensors
        self.model = models
        self.old_proto = old_proto
        self.endpoint = endpoint
        self.log_msg = log_msg
        self.buffered = buffered

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
        roles = sorted(self.model.keys())
        
        async with self.Session() as session:
            for role in roles:
                v = await self._load(session, SECTION[role], "model")
                self.model[role] = self.model[role] or PhotModel(v)
                v = await self._load(session, SECTION[role], "sensor")
                self.sensor[role] = self.sensor[role] or Sensor(v)
                v = await self._load(session, SECTION[role], "old-proto")
                self.old_proto[role] = self.old_proto[role] or bool(v)
                v = await self._load(session, SECTION[role], "endpoint")
                self.endpoint[role] = self.endpoint[role] or v
                self.photometer[role] = builder.build(self.model[role], role)
                if not self.log_msg[role]:
                    self.photometer[role].log.setLevel(logging.WARN)
                if self.buffered:
                    ring_buffer_size = int(await self._load(session, SECTION2[role], "samples"))
                    self.ring[role] = RingBuffer(ring_buffer_size)
                self.producer[role] = asyncio.create_task(self.photometer[role].readings())
               
    

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
            phot_info["sensor"] = phot_info["sensor"] or self.sensor[role].value
            phot_info["freq_offset"] = phot_info["freq_offset"] or 0.0
            return phot_info

    async def receive(self, role: Role):
        while True:
            msg = await self.photometer[role].queue.get()
            freqs=list()
            if self.buffered:
                self.ring[role].append(msg)
                freqs = self.ring[role].frequencies()
            line = f"{msg['tstamp'].strftime('%Y-%m-%d %H:%M:%S')} [{msg.get('seq')}] f={msg['freq']} Hz, tbox={msg['tamb']}, tsky={msg['tsky']}"
            progress = 1
            yield line, freqs, progress
