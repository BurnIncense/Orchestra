import logging
import json
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.paths import get_data_dir, ensure_dir


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str, log_level: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    if log_level is None:
        try:
            from utils.config import load_config
            cfg = load_config()
            log_level = cfg.get("system", {}).get("log_level", "INFO")
        except Exception:
            log_level = "INFO"

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    log_dir = ensure_dir(get_data_dir() / "logs")
    file_handler = RotatingFileHandler(
        log_dir / "orchestra.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(console_handler)

    return logger
