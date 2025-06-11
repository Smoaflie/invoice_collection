import logging
import sys

logger = logging.getLogger("BillCoector")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("[BillCollector] [%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

format_str = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s[:%(lineno)d] - %(funcName)s - %(message)s"
datefmt_str = "%y-%m-%d %H:%M:%S"
cil_handler = logging.StreamHandler(sys.stderr)  # 默认是sys.stderr
cil_handler.setLevel(logging.ERROR)
cil_handler.setFormatter(logging.Formatter(fmt=format_str, datefmt=datefmt_str))
logger.addHandler(cil_handler)
