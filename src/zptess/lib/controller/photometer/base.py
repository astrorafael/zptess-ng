# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

from abc import ABC, abstractmethod
import logging
import asyncio

from typing import Mapping, Any, Dict, Tuple, AsyncIterator


# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass

from lica.asyncio.photometer import Role, Message as PhotMessage, Model as PhotModel, Sensor
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession

# --------------
# local imports
# -------------

from ....lib.dbase.model import Config


# ----------------
# Module constants
# ----------------


SECTION = {Role.REF: "ref-device", Role.TEST: "test-device"}

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


class Controller(ABC):
    """
    Reader Controller specialized in reading the photometers
    Serves ans an interface and a base class at the same tine.
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
    ):
        self.param = {Role.REF: ref_params, Role.TEST: test_params}
        self.roles = list()
        self.Session = AsyncSession
        self.photometer = dict()
        self.ring = dict()
        self.phot_info = dict()
        self.phot_task = dict()
        if ref_params is not None:
            self.roles.append(Role.REF)
        if test_params is not None:
            self.roles.append(Role.TEST)

    # ==========
    # Public API
    # ==========

    def buffer(self, role: Role):
        return self.ring[role]

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s",
            self.__class__.__name__,
            self.roles,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        async with self.Session() as session:
            for role in self.roles:
                val_db = await self._load_config(session, SECTION[role], "model")
                val_arg = self.param[role]["model"]
                self.param[role]["model"] = val_arg if val_arg is not None else PhotModel(val_db)
                val_db = await self._load_config(session, SECTION[role], "sensor")
                val_arg = self.param[role]["sensor"]
                self.param[role]["sensor"] = val_arg if val_arg is not None else Sensor(val_db)
                val_db = await self._load_config(session, SECTION[role], "old-proto")
                val_arg = self.param[role]["old_proto"]
                self.param[role]["old_proto"] = val_arg if val_arg is not None else bool(val_db)
                val_db = await self._load_config(session, SECTION[role], "endpoint")
                val_arg = self.param[role]["endpoint"]
                self.param[role]["endpoint"] = val_arg if val_arg is not None else val_db
                self.photometer[role] = builder.build(
                    self.param[role]["model"], role, self.param[role]["endpoint"]
                )
                logging.getLogger(str(role)).setLevel(self.param[role]["log_level"])

    async def info(self, role: Role) -> Dict[str, str]:
        log = logging.getLogger(role.tag())
        try:
            phot_info = await self.photometer[role].get_info()
        except asyncio.exceptions.TimeoutError:
            log.error("Failed contacting %s photometer", role.tag())
            raise
        except Exception as e:
            log.error(e)
            raise
        else:
            phot_info["endpoint"] = role.endpoint()
            phot_info["sensor"] = phot_info["sensor"] or self.param[role]["sensor"].value
            v = phot_info["freq_offset"] or 0.0
            phot_info["freq_offset"] = float(v)
            self.phot_info[role] = phot_info
            return phot_info

    async def receive(
        self, role: Role, num_messages: int | None = None
    ) -> AsyncIterator[Tuple[Role, PhotMessage]]:
        """An asynchronous generator, to be used by clients with async for"""
        if num_messages is None:
            while True:
                msg = await self.photometer[role].queue.get()
                yield role, msg
        else:
            for i in range(num_messages):
                msg = await self.photometer[role].queue.get()
                yield role, msg

    async def write_zp(self, zero_point: float) -> float:
        """May raise asyncio.exceptions.TimeoutError in particular"""
        await self.photometer[Role.TEST].save_zero_point(zero_point)
        stored_zero_point = (await self.photometer[Role.TEST].get_info())["zp"]
        return stored_zero_point

    @abstractmethod
    async def calibrate(self) -> float:
        """Calibrate the test photometer against the refrence photometer returnoing a Zero Point"""
        pass

    # ===========
    # Private API
    # ===========

    # ----------------------------------
    # Coroutines to be turned into Tasks
    # ----------------------------------

    async def _phot_receive_task(self, role):
        """The background, long live photometer reading tasks that feed the queue"""
        log = logging.getLogger(role.tag())
        try:
            await self.photometer[role].readings()  # Endless loop inside
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("%s: %s", e.__class__.__name__, e)
        else:
            pass

    # ----------------------
    # Private helper methods
    # ----------------------

    async def _load_config(self, session: AsyncSessionClass, section: str, prop: str) -> str | None:
        q = select(Config.value).where(Config.section == section, Config.prop == prop)
        return (await session.scalars(q)).one_or_none()

    async def _launch_phot_tasks(self):
        for role in self.roles:
            self.phot_task[role] = asyncio.create_task(
                self._phot_receive_task(role), name=f"PHOT {role.tag()} TASK"
            )
            await asyncio.sleep(0)  # wait for it to be scheduled
            if self.phot_task[role].done():
                raise RuntimeError(
                    f"Background task {self.phot_task[role].get_name()} is not running"
                )
