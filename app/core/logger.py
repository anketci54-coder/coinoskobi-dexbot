from pathlib import Path
from loguru import logger
import sys

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    colorize=True,
    enqueue=True,
)

logger.add(
    LOG_DIR / "coinoskobi.log",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8",
)

def get_logger():
    return logger


if __name__ == "__main__":
    log = get_logger()
    log.info("Logger initialized successfully.")
