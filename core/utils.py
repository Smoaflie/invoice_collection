import re
from .log import logger


def extract_params_from_url(url: str, need_table_id = True):
    if need_table_id:
        match = re.search(r'/([a-zA-Z0-9]+)\?table=([a-zA-Z0-9]+)', url)
        if match:
            lark_bitable_app_token = match.group(1)
            lark_bitable_table_id = match.group(2)
            logger.debug("app_id =", lark_bitable_app_token)
            logger.debug("lark_bitable_table_id =", lark_bitable_table_id)
            return lark_bitable_app_token, lark_bitable_table_id
        else:
            logger.exception("Invalid Lark Bitable URL format.")
    else:
        match = re.search(r'/([a-zA-Z0-9]+)', url)
        if match:
            lark_bitable_app_token = match.group(1)
            logger.debug("app_id =", lark_bitable_app_token)
            return lark_bitable_app_token, None
        else:
            logger.exception("Invalid Lark Bitable URL format.")

def extract_text(obj, d):
    if obj.get(d):
        if isinstance(obj[d], str):
            return obj[d]
        else:
            return obj[d][0]['text']
    else:
        return None
