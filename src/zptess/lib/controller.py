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
import asyncio

from typing import Any, Mapping, Dict, Tuple, List, Generator


# ---------------------------
# Third-party library imports
# ----------------------------

from pubsub import pub

from typing_extensions import Self

from sqlalchemy import select

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .ring import RingBuffer
from ..lib.dbase.model import Config
from ..lib import CentralTendency

# ----------------
# Module constants
# ----------------

PhotResult = Generator[Tuple[str, List[float], int], Tuple[Self, Role], None]


SECTION1 = {Role.REF: "ref-device", Role.TEST: "test-device"}
SECTION2 = {Role.REF: "ref-stats", Role.TEST: "test-stats"}

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
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
    ):
        self.Session = AsyncSession
        self.param = {Role.REF: ref_params, Role.TEST: test_params}
        self.photometer = dict()
        self.ring = dict()
        self.phot_info = dict()
        self.roles = list()
        self.task = dict()
        if ref_params is not None:
            self.roles.append(Role.REF)
        if test_params is not None:
            self.roles.append(Role.TEST)

    def buffer(self, role: Role):
        return self.ring[role]

    async def _load(self, session, section: str, prop: str) -> str | None:
        async with session:
            q = select(Config.value).where(Config.section == section, Config.prop == prop)
            return (await session.scalars(q)).one_or_none()

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s",
            self.__class__.__name__,
            self.roles,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        async with self.Session() as session:
            for role in self.roles:
                v = await self._load(session, SECTION1[role], "model")
                self.param[role]["model"] = self.param[role]["model"] or PhotModel(v)
                v = await self._load(session, SECTION1[role], "sensor")
                self.param[role]["sensor"] = self.param[role]["sensor"] or Sensor(v)
                v = await self._load(session, SECTION1[role], "old-proto")
                self.param[role]["old_proto"] = self.param[role]["old_proto"] or bool(v)
                v = await self._load(session, SECTION1[role], "endpoint")
                self.param[role]["endpoint"] = self.param[role]["endpoint"] or v
                self.photometer[role] = builder.build(self.param[role]["model"], role)
                self.ring[role] = RingBuffer(capacity=1)
                self.task[role] = asyncio.create_task(self.photometer[role].readings())
                logging.getLogger(str(role)).setLevel(self.param[role]["log_level"])

    async def info(self, role: Role) -> Dict[str, str]:
        log = logging.getLogger(role.tag())
        try:
            phot_info = await self.photometer[role].get_info()
        except asyncio.exceptions.TimeoutError:
            log.critical("Failed contacting %s photometer", role.tag())
            raise
        except Exception as e:
            log.critical(e)
            raise
        else:
            phot_info["endpoint"] = role.endpoint()
            phot_info["sensor"] = phot_info["sensor"] or self.param[role]["sensor"].value
            v = phot_info["freq_offset"] or 0.0
            phot_info["freq_offset"] = float(v)
            self.phot_info[role] = phot_info
            return phot_info

    async def fill_buffer(self, role: Role) -> None:
        while True:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            pub.sendMessage("reading_info", controller=self, role=role, reading=msg)

    async def receive(self) -> None:
        coros = [self.fill_buffer(role) for role in self.roles]
        await asyncio.gather(*coros)


class Calibrator(Reader):
    """
    Reader Controller specialized in reading the photometers
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
        common_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params)
        self.common_param = common_params
        self.period = None
        self.central = None
        self.nrounds = None
        self.zp_fict = None
        self.zp_offset = None
        self.author = None

    async def init(self) -> None:
        await super().init()
        async with self.Session() as session:
            v = await self._load(session, SECTION2[Role.TEST], "samples")
            self.capacity = self.common_param["buffer"] or int(v)
            v = await self._load(session, SECTION2[Role.TEST], "period")
            self.period = self.common_param["period"] or float(v)
            v = await self._load(session, SECTION2[Role.TEST], "central")
            self.central = self.common_param["central"] or CentralTendency(v)
            v = await self._load(session, "calibration", "zp_fict")
            self.zp_fict = self.common_param["zp_fict"] or float(v)
            v = await self._load(session, "calibration", "rounds")
            self.nrounds = self.common_param["rounds"] or int(v)
            v = await self._load(session, "calibration", "offset")
            self.zp_offset = self.common_param["zp_offset"] or float(v)
            v = await self._load(session, "calibration", "author")
            self.author = self.common_param["author"] or v
        self.dry_run = self.common_param["dry_run"]
        self.update = self.common_param["update"]
        self.ring[Role.REF] = RingBuffer(capacity=self.capacity, central=self.central)
        self.ring[Role.TEST] = RingBuffer(capacity=self.capacity, central=self.central)

    async def producer_task(self, role: Role) -> None:
        log = logging.getLogger(role.tag())
        while not self.is_calibrated:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            log.info("CUCU")

    async def fill_buffer(self, role: Role) -> None:
        while len(self.ring[role]) < self.capacity:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            pub.sendMessage("reading_info", controller=self, role=role, reading=msg)

    def magnitude(self, role: Role, freq: float):
        return self.zp_fict - 2.5 * math.log10(freq - self.phot_info[role]["freq_offset"])

    async def statistics(self):
        # the range boundary is not an error
        for i in range(1, self.nrounds + 1):
            log.info("ROUND %d/%d", i, self.nrounds)
            ref_freq, ref_stdev = self.ring[Role.REF].statistics()
            test_freq, test_stdev = self.ring[Role.REF].statistics()
            ref_mag = self.magnitude(Role.REF, ref_freq)
            test_mag = self.magnitude(Role.TEST, test_freq)
            mag_diff = ref_mag - test_mag
            await asyncio.sleep(10)
        self.is_calibrated = True

    async def calibrate(self) -> None:
        coros = [self.fill_buffer(role) for role in self.roles]
        # Waiting for both circular buffers to be filled
        await asyncio.gather(*coros)
        self.producer = [None, None]
        # background task that fill the circular buffers while we perform
        # the calibratu¡ion rounds
        self.producer[Role.REF] = asyncio.create_task(self.producer_task(Role.REF))
        self.producer[Role.TEST] = asyncio.create_task(self.producer_task(Role.TEST))
        self.is_calibrated = False
        await asyncio.gather(self.statistics(), *self.producer)
