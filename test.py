import fitz
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

from api import *

token = "GOvAbKyv3aOot1sy9emcTmpdn6d"
table_id = "tblgP75665t0WrOQ"


def get_qrcode(file_path):
    """提取pdf文件中左上角的二维码并识别"""
    pdfDoc = fitz.open(file_path)
    page = pdfDoc[0]  # 只对第一页的二维码进行识别
    mat = fitz.Matrix(3.0, 3.0).prerotate(0)
    # rect = page.rect
    # mp = rect.tl + (rect.br - rect.tl) * 1 / 4
    # clip = fitz.Rect(rect.tl, mp)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    barcodes = decode(img, symbols=[ZBarSymbol.QRCODE])
    for barcode in barcodes:
        result = barcode.data.decode("utf-8")
        return result


def DEBUG_OUT(data=None, json=None, file="request.json"):
    """调试时输出数据到文件中."""
    with open(file, "w", encoding="gbk", errors="replace") as f:
        json_str = (
            ujson.dumps(
                data, indent=4, ensure_ascii=False, escape_forward_slashes=False
            )
            if data
            else json
        )  # 格式化写入 JSON 文件
        f.write(json_str)
