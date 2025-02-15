from datetime import datetime

class Controller:
	async def open(comment: str|None) -> datetime:
		pass

	async def close() -> None:
		pass

	async def purge() -> None:
		pass

	async def export(path: str) -> None:
		pass
