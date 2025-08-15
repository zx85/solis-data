# logger.py
import logging

# Configure the root logger here
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

# Export a shared logger instance
log = logging.getLogger("solis")
