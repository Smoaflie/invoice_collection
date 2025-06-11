import os

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
