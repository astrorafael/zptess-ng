# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------
import logging

from datetime import datetime, timezone

# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select, func

from lica.sqlalchemy.asyncio.dbase import AsyncSession

# --------------
# local imports
# -------------

from ..dbase.model import Batch, SummaryView

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])


class Controller:
    def __init__(self):
        self.Session = AsyncSession

    async def open(self, comment: str | None) -> datetime:
        begin_tstamp = datetime.now(timezone.utc).replace(microsecond=0)
        async with self.Session() as session:
            async with session.begin():
                await self._assert_closed(session)
                batch = Batch(
                    begin_tstamp=begin_tstamp, end_tstamp=None, email_sent=False, comment=comment
                )
                session.add(batch)
        return begin_tstamp

    async def is_open(self) -> bool:
        async with self.Session() as session:
            return await self._is_open(session)

    async def close(self) -> datetime:
        end_tstamp = datetime.now(timezone.utc).replace(microsecond=0)
        async with self.Session() as session:
            async with session.begin():
                await self._assert_open(session)
                q = select(func.count(SummaryView.session)).where(SummaryView.upd_flag == True)  # noqa: E712
                _ = (await session.scalars(q)).one()
                batch = await self._latest_batch(session)
                batch.end_tstamp = end_tstamp
                batch.email_sent = False
                batch.calibrations = 999
                session.add(batch)
        return end_tstamp

    async def purge(self) -> None:
        pass

    async def export(self, path: str) -> None:
        pass

    # ----------------
    # Helper functions
    # ----------------

    async def _is_open(
        self,
        session: AsyncSession,
    ) -> bool:
        q = select(func.count(Batch.begin_tstamp)).where(Batch.end_tstamp.is_(None))
        count = (await session.scalars(q)).one()
        return count > 0

    async def _latest_batch(
        self,
        session: AsyncSession,
    ) -> Batch | None:
        q = select(Batch).where(Batch.end_tstamp.is_(None))
        batch = (await session.scalars(q)).one_or_none()
        return batch

    async def _assert_closed(
        self,
        session: AsyncSession,
    ) -> None:
        already_open = await self._is_open(session)
        if already_open:
            raise RuntimeError("There is an already open session")

    async def _assert_open(
        self,
        session: AsyncSession,
    ) -> None:
        already_open = await self._is_open(session)
        if not already_open:
            raise RuntimeError("There is an already open session")
