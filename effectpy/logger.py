from __future__ import annotations
import sys, datetime as _dt, json
from typing import Optional, Dict, Any
from .layer import from_resource
from .context import Context

try:
    # Pull correlation ids if tracer is loaded
    from .tracer import current_trace_id, current_span_id
except Exception:  # pragma: no cover - optional import
    def current_trace_id() -> Optional[str]: return None
    def current_span_id() -> Optional[str]: return None


_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


class ConsoleLogger:
    def __init__(self, name: str = "effectpy", level: str = "INFO", json_output: bool = False, context: Optional[Dict[str, Any]] = None):
        self.name = name
        self.level = _LEVELS.get(level.upper(), 20)
        self.json_output = json_output
        self.context = dict(context or {})

    def set_level(self, level: str) -> None:
        self.level = _LEVELS.get(level.upper(), self.level)

    def bind(self, **fields: Any) -> "ConsoleLogger":
        ctx = dict(self.context); ctx.update(fields)
        return ConsoleLogger(self.name, level=self.level_name, json_output=self.json_output, context=ctx)

    @property
    def level_name(self) -> str:
        for k, v in _LEVELS.items():
            if v == self.level: return k
        return "INFO"

    async def _log(self, level: str, msg: str, **fields: Any) -> None:
        if _LEVELS[level] < self.level:
            return
        ts = _dt.datetime.utcnow().isoformat()
        data = {
            "ts": ts,
            "name": self.name,
            "level": level,
            "msg": msg,
        }
        # correlation ids
        tid = current_trace_id(); sid = current_span_id()
        if tid: data["trace_id"] = tid
        if sid: data["span_id"] = sid
        # merge contexts
        all_fields: Dict[str, Any] = {}
        all_fields.update(self.context)
        all_fields.update(fields)
        if self.json_output:
            if all_fields:
                data["fields"] = all_fields
            print(json.dumps(data, separators=(",", ":")), file=sys.stderr)
        else:
            extras = "".join([f" {k}={v}" for k, v in sorted(all_fields.items())]) if all_fields else ""
            corr = "" if not tid and not sid else f" trace_id={tid} span_id={sid}"
            print(f"[{ts}] {self.name} {level}: {msg}{corr}{extras}", file=sys.stderr)

    async def debug(self, msg: str, **fields: Any) -> None: await self._log("DEBUG", msg, **fields)
    async def info(self, msg: str, **fields: Any) -> None: await self._log("INFO", msg, **fields)
    async def warn(self, msg: str, **fields: Any) -> None: await self._log("WARN", msg, **fields)
    async def error(self, msg: str, **fields: Any) -> None: await self._log("ERROR", msg, **fields)


async def _mk_logger(_ctx: Context) -> ConsoleLogger: return ConsoleLogger()
async def _close_logger(_l: ConsoleLogger) -> None: return None
LoggerLayer = from_resource(ConsoleLogger, _mk_logger, _close_logger)
