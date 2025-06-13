import logging
import sys

logger = logging.getLogger("BillCoector")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(filename)s[:%(lineno)d] - %(message)s"
    ))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
