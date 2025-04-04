
# ---------------------
# Third party libraries
# ---------------------

from sqlalchemy import select
from lica.sqlalchemy.asyncio.dbase import AsyncSession

# -------------
# Own Libraries
# -------------

from ...dbase.model import Batch

# Re-exports
from .batch import Controller as Controller

async def get_open_batch(session: AsyncSession) -> Batch | None:
        """Used by the persistent controller"""
        q = select(Batch).where(Batch.end_tstamp.is_(None))
        batch = (await session.scalars(q)).one_or_none()
        return batch