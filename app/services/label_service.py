"""
LabelService — barcode label PDF and ZPL generation.

Produces:
  - Print-ready A4 PDF with labels in configurable grid layouts.
  - ZPL II strings for direct thermal label printing (Zebra, Godex, etc.).

PDF Templates:
  'standard' — 4 per row  (default, matches sample layout)
  'compact'  — 5 per row  (mini stickers)
  'large'    — 3 per row  (bigger labels with more detail)

Architecture note:
    LabelService is the single extension point for all print output formats.
    To add ESC/P or other languages, add a new @staticmethod here.
"""

import base64
import os
import shutil
import tempfile

import pdfkit
from flask import render_template, current_app

from app.models import SystemSetting
from app.services.barcode_service import BarcodeService
from app.utils import format_currency


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

LABEL_TEMPLATES = {
    'standard': 'products/label_print.html',
    'compact':  'products/label_print_compact.html',
    'large':    'products/label_print_large.html',
}

TEMPLATE_LABELS = {
    'standard': 'Standard — 3/row',
    'compact':  'Compact  — 4/row',
    'large':    'Large    — 2/row',
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_label_settings() -> dict:
    """Read label display preferences from SystemSetting."""
    return {
        'show_price':      SystemSetting.get('label_show_price',   'true')  == 'true',
        'show_sku':        SystemSetting.get('label_show_sku',     'true')  == 'true',
        'show_company':    SystemSetting.get('label_show_company', 'false') == 'true',
        'company_name':    SystemSetting.get('company_name', ''),
        'currency_symbol': SystemSetting.get('currency_symbol', '$'),
    }


def _build_label_list(label_items: list) -> list:
    """
    Convert {'product', 'copies'} dicts into a flat label-render list.

    Barcode images are generated and encoded as base64 data URIs — embedded
    directly in the HTML so wkhtmltopdf needs no file-system access at all.
    This is the most reliable approach across all wkhtmltopdf versions and OS.
    """
    settings = _get_label_settings()
    labels = []

    for item in label_items:
        product = item['product']
        copies  = max(1, int(item.get('copies', 1)))

        barcode_b64 = None
        if product.barcode:
            try:
                img_bytes = BarcodeService.generate_barcode_image(
                    product.barcode,
                    product.barcode_type or 'Code128',
                    options={
                        'module_width':  0.4,    # 4.7px/module at 300 dpi — reliably scannable
                        'module_height': 15.0,   # taller bars (was 9.0)
                        'quiet_zone':    6.0,    # ISO quiet zone ≥10× module width (was 2.5)
                        'write_text':    False,  # barcode number rendered in HTML, not in PNG
                        'dpi':           300,    # high-resolution source PNG (was 200)
                        'background':    'white',
                        'foreground':    'black',
                    },
                )
                if img_bytes:
                    barcode_b64 = base64.b64encode(img_bytes).decode('ascii')
                else:
                    current_app.logger.warning(
                        'LabelService: generate_barcode_image returned empty for product %s',
                        product.id,
                    )
            except Exception as exc:
                current_app.logger.warning(
                    'LabelService: barcode image failed for product %s: %s',
                    product.id, exc,
                )

        label = {
            'product_name':  product.name,
            'barcode_value': product.barcode or '',
            'barcode_b64':   barcode_b64,
            'price_str':     format_currency(product.selling_price) if settings['show_price'] else None,
            'sku':           product.sku if settings['show_sku'] else None,
            'company_name':  settings['company_name'] if settings['show_company'] else None,
        }

        for _ in range(copies):
            labels.append(label)

    return labels


def _render_pdf(tpl_name: str, labels: list) -> bytes:
    """
    Render label HTML then convert to PDF via wkhtmltopdf.

    Strategy (most reliable cross-platform):
      1. Render HTML with base64-embedded barcode images (no file-system deps).
      2. Write HTML to a temp file so wkhtmltopdf has a proper file:// context.
      3. Call pdfkit.from_file() — avoids stdin/from_string quirks on Windows.
      4. Always clean up the temp file in a finally block.
    """
    html    = render_template(tpl_name, labels=labels)
    tmpdir  = tempfile.mkdtemp(prefix='elpos_lbl_')

    try:
        html_path = os.path.join(tmpdir, 'labels.html')
        with open(html_path, 'w', encoding='utf-8') as fh:
            fh.write(html)

        wk_path = current_app.config.get('WKHTMLTOPDF_PATH')
        config  = pdfkit.configuration(wkhtmltopdf=wk_path)

        options = {
            'page-size':                'A4',
            'margin-top':               '8mm',
            'margin-right':             '5mm',
            'margin-bottom':            '8mm',
            'margin-left':              '5mm',
            'encoding':                 'UTF-8',
            'no-outline':               None,
            'quiet':                    None,
            'enable-local-file-access': None,
            'dpi':                      '96',
            'zoom':                     '1',
            'print-media-type':         None,
            'disable-smart-shrinking':  None,
        }

        return pdfkit.from_file(html_path, False, configuration=config, options=options)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class LabelService:

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_labels_pdf(label_items: list, template: str = 'standard') -> bytes:
        """
        Generate a print-ready A4 PDF containing all requested labels.

        Args:
            label_items: list of {'product': Product, 'copies': int} dicts.
            template:    layout key — 'standard' | 'compact' | 'large'.

        Returns:
            Raw PDF bytes.  Raises on wkhtmltopdf failure.
        """
        tpl_name = LABEL_TEMPLATES.get(template, LABEL_TEMPLATES['standard'])
        labels   = _build_label_list(label_items)
        return _render_pdf(tpl_name, labels)

    @staticmethod
    def generate_single_label_pdf(
        product,
        copies: int = 1,
        template: str = 'standard',
    ) -> bytes:
        """Convenience wrapper for a single product."""
        return LabelService.generate_labels_pdf(
            [{'product': product, 'copies': copies}],
            template=template,
        )

    # ------------------------------------------------------------------
    # ZPL II generation  (Zebra / thermal label printers)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_labels_zpl(
        label_items: list,
        label_width_mm:  int = 62,
        label_height_mm: int = 36,
        dpi:             int = 203,
    ) -> str:
        """
        Generate ZPL II markup for all requested labels.

        ZPL II is the native language of Zebra and compatible thermal label
        printers.  The output can be sent directly to a printer via:

          * Windows USB/LAN:  ``copy labels.zpl \\\\PRINTERHOST\\SHARE``
          * Python socket:    ``sock.sendall(zpl.encode())`` to TCP port 9100
          * Linux:            ``lpr -P PRINTERNAME labels.zpl``

        Args:
            label_items:      list of {'product', 'copies'} dicts.
            label_width_mm:   label width  in millimetres (default 62).
            label_height_mm:  label height in millimetres (default 36).
            dpi:              printer DPI — 203 (standard) or 300 (HD).

        Returns:
            ZPL II string — save as .zpl and send to printer port 9100.
        """
        settings = _get_label_settings()

        dpm = dpi / 25.4           # dots per mm
        lw  = int(label_width_mm  * dpm)
        lh  = int(label_height_mm * dpm)

        chunks = []

        for item in label_items:
            product = item['product']
            copies  = max(1, int(item.get('copies', 1)))
            price_str = format_currency(product.selling_price) if settings['show_price'] else None

            for _ in range(copies):
                z = ['^XA']                        # start label
                z.append(f'^PW{lw}')               # print width (dots)
                z.append(f'^LL{lh}')               # label length (dots)
                z.append('^LH0,0')                 # label home origin

                y = 10   # Y cursor (dots)

                # Company name
                if settings['show_company'] and settings['company_name']:
                    co = settings['company_name'][:32]
                    z.append(f'^FO15,{y}^A0N,14,14^FD{co}^FS')
                    y += 20

                # Product name (truncate to ~28 chars)
                name = product.name
                if len(name) > 28:
                    name = name[:27] + '\u2026'
                z.append(f'^FO15,{y}^A0N,20,20^FD{name}^FS')
                y += 28

                # Barcode (EAN-13 for 12/13-digit numeric; Code128 otherwise)
                if product.barcode:
                    val = product.barcode
                    if val.isdigit() and len(val) in (12, 13):
                        bc_cmd = '^BEA,40,Y,2,D'    # EAN-13
                    else:
                        bc_cmd = '^BCN,40,Y,N,N,N'  # Code128
                    z.append(f'^FO15,{y}{bc_cmd}^FD{val}^FS')
                    y += 58

                # Footer row: SKU (left) + price (right)
                if settings['show_sku'] and product.sku:
                    z.append(f'^FO15,{y}^A0N,14,14^FDSKU:{product.sku}^FS')
                if price_str:
                    px = max(lw - int(len(price_str) * 13) - 15, lw // 2)
                    z.append(f'^FO{px},{y}^A0N,18,18^FD{price_str}^FS')

                z.append('^XZ')                    # end label
                chunks.append('\n'.join(z))

        return '\n\n'.join(chunks)

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_template_choices() -> list:
        """Return [(key, label), ...] list for use in template selectors."""
        return [(k, TEMPLATE_LABELS[k]) for k in LABEL_TEMPLATES]
