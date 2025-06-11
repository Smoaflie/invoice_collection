import os
import logging

# Directory Management
try:
    # Run in Terminal
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
except:
    # Run in ipykernel & interactive
    ROOT_DIR = os.getcwd()
DB_DIR = os.path.join(ROOT_DIR, "invoices.db")
TMP_DIR = os.path.join(ROOT_DIR, "Temp")
OUTPUT_DIR = os.path.join(ROOT_DIR, "Output")
CONFIG_DIR = os.path.join(ROOT_DIR, "config.json")
FILES_PATH = os.path.join(ROOT_DIR, "cache")

# Logger
format_str = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s[:%(lineno)d] - %(funcName)s - %(message)s"
datefmt_str = "%y-%m-%d %H:%M:%S"
cil_handler = logging.StreamHandler(os.sys.stderr)  # 默认是sys.stderr
cil_handler.setLevel(logging.INFO)  # TODO: 会被BasicConfig限制？(过滤树)
cil_handler.setFormatter(logging.Formatter(fmt=format_str, datefmt=datefmt_str))
