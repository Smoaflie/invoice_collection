import json
import os
from core.log import logger

class I18n:
    def __init__(self, lang_code='en', lang_dir='i18n'):
        self.lang_code = lang_code
        self.lang_dir = lang_dir
        self.translations = {}
        self._load_language()

    def _load_language(self):
        file_path = os.path.join(self.lang_dir, f"{self.lang_code}.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            logger.exception(f"[ERROR] Language file {file_path} not found. Using empty fallback.")
            self.translations = {}

    def t(self, key):
        return self.translations.get(key, f"{key}")