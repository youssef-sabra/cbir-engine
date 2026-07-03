"""Structured (JSON) logging setup, identical across all services.

Centralized here so every service emits the same log shape for the future
log-aggregation stack (docs/ARCHITECTURE.md Section 12) without each service
reinventing formatter details. Never log raw image bytes or credentials.
"""

from __future__ import annotations

import json
import logging
import sys


class JsonLogFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(service_name: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(service_name))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
