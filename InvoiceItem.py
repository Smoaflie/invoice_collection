import os
import logging
import json
import shutil
import tkinter as tk
import tkinter.messagebox as msgbox
from tkinter import filedialog
from pathlib import Path
from typing import Optional
import windnd
import fitz  # fitz就是pip install PyMuPDF
from pyzbar.pyzbar import decode
from PIL import Image
from InvoiceParser import InvoiceParser
from InvoiceDB import InvoiceDB

from config import FILES_PATH, cil_handler, OUTPUT_DIR, TMP_DIR, DB_DIR


def pdf2imgfile(pdfPath, imagePath="", prefix=""):
    """
    description: convert pdf to imgs and save to imagePath
    param {*} pdfPath: pdf file dir
    param {*} imagePath: output folder of imgs
    return {*}
    """
    # TODO: When pystand start from Xmind, this function will collapse.
    # startTime_pdf2img = datetime.datetime.now()  # 开始时间
    pdfDoc = fitz.open(pdfPath)
    for pg in range(pdfDoc.page_count):
        page = pdfDoc[pg]
        rotate = int(0)
        # 每个尺寸的缩放系数为，这将为我们生成分辨率提高的图像。
        # 此处若是不做设置，若图片大小为：792X612, dpi=96, (1.33333333-->1056x816)   (2-->1584x1224)
        # TODO: 默认大小？
        zoom_x = 2
        zoom_y = 2
        mat = fitz.Matrix(zoom_x, zoom_y).prerotate(rotate)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if not os.path.exists(imagePath):
            os.makedirs(imagePath)
        output_dir = os.path.join(imagePath, prefix + "invoice_%s.png" % pg)
        pix.save(output_dir, "png")
    # endTime_pdf2img = datetime.datetime.now()  # 结束时间
    # global_logger.info('file saved to ' + os.path.relpath(output_dir) +
    #                    ' | time: %f' % (endTime_pdf2img - startTime_pdf2img).seconds)


def pdf2img(pdfPath, jpg_quality=20):
    """
    description: convert pdf to imgs
    param {*} pdfPath: pdf file dir
    return {*} pix_list: list of imgs
    """
    pdfDoc = fitz.open(pdfPath)
    if os.path.isdir(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.mkdir(TMP_DIR)
    pix_list = []
    for pg in range(pdfDoc.page_count):
        page = pdfDoc[pg]
        rotate = int(0)
        # 每个尺寸的缩放系数为，这将为我们生成分辨率提高的图像。
        # 此处若是不做设置，若图片大小为：792X612, dpi=96, (1.33333333-->1056x816)   (2-->1584x1224)
        # TODO: 默认大小？
        zoom_x = 2
        zoom_y = 2
        mat = fitz.Matrix(zoom_x, zoom_y).prerotate(rotate)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        # TODO: returning pix directly takes up to much space
        # name = os.path.join(TMP_DIR, 'invoice_%s.png' % pg)
        # pix.save(name, 'png')
        # pix_list.append(name)

        # pix_list.append(pix)

        # Shrink the image
        pix_list.append(pix.tobytes(output="jpg", jpg_quality=jpg_quality))
    return pix_list


class InvoiceItem(dict):

    db = InvoiceDB(DB_DIR)

    InvoiceState = {
        "DROPPED": -1,  # 放弃
        "UNSUBMITTED": 0,  # 未提交
        "SUBMITTED": 1,  # 已提交
        "COMPLETED": 2,  # 已完成
    }

    def __init__(
        self,
        name: str = None,
        invoice_origin_dir=None,
        order_origin_dir=None,
        transfer_origin_dir=None,
        uploader: str = None,
        record_index: int = None,
        remark: str = None,
        data: dict = None,
    ):
        self.logger = logging.getLogger("InvoiceItem")
        self.logger.addHandler(cil_handler)
        self.record_index = record_index
        self.uploader = uploader
        self.remark = remark
        if data:  # Load from data
            self.INVOICE_CODE = data["basic_info"]["invoice_code"]
            self.INVOICE_TOTAL_AMOUNT = data["total_amount"]
            self.INVOICE_DATE = data["basic_info"]["date"]
            self.state = data.get("state", 0)
        else:  # Load from App
            self.name = ""
            self.state = InvoiceItem.InvoiceState["UNSUBMITTED"]  # Invoice state
            # Relpath of files
            self.INVOICE_DIR = ""  # self.invoice
            self.ORDER_DIR = ""  # self.order
            self.TRANSFER_DIR = ""  # self.transfer
            # Invoice Info
            self.INVOICE_CODE = ""
            self.INVOICE_TOTAL_AMOUNT = ""
            self.INVOICE_DATE = ""
            # If not imported, error is raised.
            self.INFO_IMPORTED = False

            if name:
                self.name = name
            self.read_invoice_info(invoice_origin_dir)
            self.order_origin_dir = order_origin_dir
            self.transfer_origin_dir = transfer_origin_dir
            self.itemfiles_check()

    def edit(
        self,
        name: str = None,
        invoice_origin_dir=None,
        order_origin_dir=None,
        transfer_origin_dir=None,
    ):
        if name:
            self["name"] = name
        self.read_invoice_info(invoice_origin_dir)
        self.order_origin_dir = order_origin_dir
        self.transfer_origin_dir = transfer_origin_dir
        self.itemfiles_check()

    def abspath(self, filename):
        """
        description: Generate abspath using database relative path
        param {*} self
        param {*} dbpath
        return {*} abspath
        """
        return os.path.join(FILES_PATH, filename)

    def itemfiles_check(self):
        """
        description: clear recorded dbpath matching no file and delete files not recorded.
        param {*} self
        return {*}
        """
        files = []
        unreachable_files = []
        if os.path.isfile(self.abspath(self.INVOICE_DIR)):
            files.append(self.abspath(self.INVOICE_DIR))
        else:
            unreachable_files.append(self.abspath(self.INVOICE_DIR))
        if os.path.isfile(self.abspath(self.ORDER_DIR)):
            files.append(self.abspath(self.ORDER_DIR))
        else:
            unreachable_files.append(self.abspath(self.ORDER_DIR))
        if os.path.isfile(self.abspath(self.TRANSFER_DIR)):
            files.append(self.abspath(self.TRANSFER_DIR))
        else:
            unreachable_files.append(self.abspath(self.TRANSFER_DIR))
        self.logger.debug("files detected:%s", " | ".join(files))
        if unreachable_files:
            self.logger.error("unreachable files:%s", " | ".join(unreachable_files))

    def read_invoice_info(self, invoice_path=""):
        if not invoice_path:
            raise ValueError("Try read invoice with error: Empty file path.")
        invoice_path = self.abspath(self[self.INVOICE_DIR])
        if invoice_path.startswith("#"):  # Manual import
            # format "# CODE NUMBER VALUE DATE VERI "
            # e.g. "# 20220824 07016763646873251240 100.00"
            self.logger.debug("manual import:%s", invoice_path)
            info_list = invoice_path[1:].strip().split(" ")
            if len(info_list) == 3 and len(info_list[0]) == 8:
                self.INVOICE_DATE = info_list[0]
                self.INVOICE_CODE = info_list[1]
                self.INVOICE_TOTAL_AMOUNT = info_list[2]
            else:
                self.logger.error("Info check failed.")
        elif (
            os.path.isfile(invoice_path) and os.path.splitext(invoice_path)[1] == ".pdf"
        ):
            parser = InvoiceParser(invoice_path)
            info = parser.parse()
            # Invoice Info
            self.INVOICE_CODE = info["basic_info"]["invoice_code"]
            self.INVOICE_TOTAL_AMOUNT = info["total_amount"]
            self.INVOICE_DATE = info["basic_info"]["date"]
        else:
            raise Exception("read_invoice_info failed.")

    def save_to_db(self):
        return InvoiceItem.db.update_invoice_state(self.INVOICE_CODE, self.state)

    # Output
    def file_output(self, src, dstdir=OUTPUT_DIR, prefix=""):
        """
        description:
        param {*} self
        param {*} src: abspath of srcfile
        param {*} dst: abspath of dstfile
        return {*}
        """
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        ext = os.path.splitext(src)[1]
        if ext == ".pdf":
            pdf2imgfile(src, dstdir, prefix)
        elif ext == ".jpg" or ext == ".png":
            shutil.copy(src, os.path.join(dstdir, prefix + os.path.basename(src)))
        else:
            self.logger.error("Unkown file format:%s", src)

    def invoice_files_output(self, prefix=""):
        """
        description: Output files of an invoice item
        param {*} self
        return {*}
        """
        if self.INVOICE_DIR and not self.INVOICE_DIR.startswith("#"):
            self.file_output(self.abspath(self.INVOICE_DIR), prefix=prefix)
        if self.ORDER_DIR:
            self.file_output(self.abspath(self.ORDER_DIR), prefix=prefix)
        if self.TRANSFER_DIR:
            self.file_output(self.abspath(self.TRANSFER_DIR), prefix=prefix)

    def invoice_files_output_pdf(self, doc, jpg_quality=20, footnote_prefix=""):
        page = doc.new_page()  # Create a new page(Default A4)
        width = page.mediabox.x1 - page.mediabox.x0
        height = page.mediabox.y1 - page.mediabox.y0
        marginx = 40
        marginy = 10
        binding_height = 60
        footnote_height = 20
        content_rect = fitz.Rect(
            marginx, marginy, width - marginx, binding_height + marginy
        )
        page.insert_textbox(
            content_rect, "Binding Area", fontsize=20, align=fitz.TEXT_ALIGN_CENTER
        )
        page.draw_rect(content_rect, color=(0, 0, 0), width=1)
        content_rect = fitz.Rect(
            marginx,
            height - footnote_height - marginy,
            width - marginx,
            height - marginy,
        )
        page.insert_textbox(
            content_rect,
            "|".join([footnote_prefix, self[self.INVOICE_DATE], self["name"]]),
            fontsize=10,
            fontname="china-s",
        )

        if self[self.ORDER_DIR]:
            content_rect = fitz.Rect(
                marginx,
                int(height / 2) + marginy,
                int(width / 2) - marginx,
                height - footnote_height - marginy,
            )
            pix = fitz.Pixmap(self.abspath(self[self.ORDER_DIR]))
            page.insert_image(
                content_rect, stream=pix.tobytes("jpg", jpg_quality=jpg_quality)
            )
        if self[self.TRANSFER_DIR]:
            content_rect = fitz.Rect(
                int(width / 2) + marginx,
                int(height / 2) + marginy,
                width - marginx,
                height - footnote_height - marginy,
            )
            pix = fitz.Pixmap(self.abspath(self[self.TRANSFER_DIR]))
            page.insert_image(
                content_rect, stream=pix.tobytes("jpg", jpg_quality=jpg_quality)
            )

        if self[self.INVOICE_DIR]:
            content_rect = fitz.Rect(
                marginx,
                binding_height + marginy,
                width - marginx,
                int(height / 2) - marginy,
            )
            if self[self.INVOICE_DIR].startswith("#"):
                page.insert_textbox(
                    content_rect,
                    "\nPaper Invoice\n"
                    + "\n".join(self[self.INVOICE_DIR][1:].split(" ")),
                    fontsize=20,
                    align=fitz.TEXT_ALIGN_CENTER,
                )
            else:
                pix_list = pdf2img(self.abspath(self[self.INVOICE_DIR]), jpg_quality)
                page.insert_image(content_rect, stream=pix_list[0])
                for pix in pix_list[1:]:
                    page = doc.new_page()  # Create a new page(Default A4)
                    content_rect = fitz.Rect(
                        marginx, marginy, width - marginx, height - marginy
                    )
                    page.insert_image(content_rect, stream=pix)
