from __future__ import annotations
import sys, datetime as _dt
from .layer import from_resource
from .context import Context

class ConsoleLogger:
    def __init__(self, name: str = "effectpy"): self.name = name
    async def _log(self, level: str, msg: str) -> None:
        ts = _dt.datetime.utcnow().isoformat(); print(f"[{ts}] {self.name} {level}: {msg}", file=sys.stderr)
    async def debug(self, msg: str) -> None: await self._log("DEBUG", msg)
    async def info(self, msg: str) -> None: await self._log("INFO", msg)
    async def warn(self, msg: str) -> None: await self._log("WARN", msg)
    async def error(self, msg: str) -> None: await self._log("ERROR", msg)

async def _mk_logger(_ctx: Context) -> ConsoleLogger: return ConsoleLogger()
async def _close_logger(_l: ConsoleLogger) -> None: return None
LoggerLayer = from_resource(ConsoleLogger, _mk_logger, _close_logger)
