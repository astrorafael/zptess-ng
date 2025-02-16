from datetime import datetime

from lica.sqlalchemy.asyncio.dbase import AsyncSession


class Controller:
    def __init__(self):
        self.Session = AsyncSession

    async def open(comment: str | None) -> datetime:
        pass

    async def close() -> None:
        pass

    async def purge() -> None:
        pass

    async def export(path: str) -> None:
        pass
