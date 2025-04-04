# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass

# --------------
# local imports
# -------------

from ...lib.dbase.model import Config

async def load_config(session: AsyncSessionClass, section: str, prop: str) -> str | None:
    q = select(Config.value).where(Config.section == section, Config.prop == prop)
    return (await session.scalars(q)).one_or_none()