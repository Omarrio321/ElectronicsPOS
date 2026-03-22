"""
BarcodeService — central, concurrency-safe barcode generation and management.

Design rules:
  - Internal barcodes follow the format: <PREFIX>-<PADDED_SEQUENCE>  (e.g. EP-00000001)
  - Sequence is incremented atomically using SELECT … FOR UPDATE row locking.
  - Supplier / manually-entered barcodes are preserved; never overwritten automatically.
  - barcode_type  : 'Code128' | 'EAN13' | 'UPCA'
  - barcode_source: 'generated' | 'manual' | 'supplier'
"""

from io import BytesIO
from datetime import datetime

import barcode as python_barcode
from barcode.writer import ImageWriter

from app import db
from app.models import BarcodeSequence, Product, SystemSetting


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_settings():
    """Return (prefix, padding) from SystemSetting, with safe defaults."""
    prefix = (SystemSetting.get('barcode_prefix', 'EP') or 'EP').strip().upper()
    try:
        padding = int(SystemSetting.get('barcode_padding', '8'))
        padding = max(4, min(padding, 12))
    except (ValueError, TypeError):
        padding = 8
    return prefix, padding


def _detect_barcode_type(value: str) -> str:
    """
    Heuristic detection of barcode symbology from the value string.
    Falls back to Code128 for anything non-numeric or non-standard length.
    """
    if not value:
        return 'Code128'
    digits_only = value.isdigit()
    if digits_only and len(value) in (12, 13):
        return 'EAN13'
    if digits_only and len(value) in (11, 12):
        return 'UPCA'
    return 'Code128'


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class BarcodeService:

    # ------------------------------------------------------------------
    # Sequence management
    # ------------------------------------------------------------------

    @staticmethod
    def generate_next_barcode() -> str:
        """
        Generate the next unique internal barcode atomically.

        Uses SELECT … FOR UPDATE to prevent duplicate sequences under
        concurrent requests (MySQL InnoDB row-level locking).

        Returns the formatted barcode string, e.g. 'EP-00000001'.
        The caller is responsible for committing the transaction.
        """
        prefix, padding = _get_settings()

        # Lock the row for this prefix
        seq = (
            db.session.query(BarcodeSequence)
            .filter_by(prefix=prefix)
            .with_for_update()
            .first()
        )

        if seq is None:
            # First ever generation with this prefix — insert then re-lock
            seq = BarcodeSequence(prefix=prefix, last_sequence=0)
            db.session.add(seq)
            db.session.flush()
            seq = (
                db.session.query(BarcodeSequence)
                .filter_by(prefix=prefix)
                .with_for_update()
                .first()
            )

        seq.last_sequence += 1
        seq.updated_at = datetime.utcnow()
        db.session.flush()  # flush so the incremented value is visible within the transaction

        return f"{prefix}-{seq.last_sequence:0{padding}d}"

    # ------------------------------------------------------------------
    # Product barcode assignment
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_product_barcode(product: Product) -> bool:
        """
        Auto-generate an internal barcode for *product* if it has none.

        Returns True if a barcode was generated, False if one already existed.
        Does NOT commit — caller must commit.
        """
        if product.barcode:
            return False

        barcode_value = BarcodeService.generate_next_barcode()
        product.barcode = barcode_value
        product.barcode_type = 'Code128'
        product.barcode_source = 'generated'
        return True

    @staticmethod
    def apply_manual_barcode(product: Product, value: str) -> None:
        """
        Assign a manually entered or scanned barcode to *product*.

        Sets barcode_source='manual' and auto-detects barcode_type.
        Does NOT commit — caller must commit.
        """
        value = value.strip()
        product.barcode = value
        product.barcode_type = _detect_barcode_type(value)
        product.barcode_source = 'manual'

    @staticmethod
    def mark_as_supplier_barcode(product: Product) -> None:
        """
        Re-classify the product's existing barcode as supplier-originated.
        Useful after import flows where supplier barcodes are provided.
        Does NOT commit.
        """
        if product.barcode:
            product.barcode_source = 'supplier'
            if not product.barcode_type:
                product.barcode_type = _detect_barcode_type(product.barcode)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def is_barcode_unique(value: str, exclude_product_id: int = None) -> bool:
        """
        Return True if *value* is not already assigned to any other product.
        Optionally exclude the product being edited (by its ID).
        """
        q = Product.query.filter(Product.barcode == value)
        if exclude_product_id:
            q = q.filter(Product.id != exclude_product_id)
        return q.first() is None

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_barcode_image(
        barcode_value: str,
        barcode_type: str = 'Code128',
        options: dict = None,
    ) -> bytes:
        """
        Render a barcode as a PNG image and return raw bytes.

        Falls back to Code128 if the requested symbology fails
        (e.g. EAN13 with non-numeric or wrong-length input).
        """
        default_options = {
            'module_width': 0.22,
            'module_height': 9.0,
            'quiet_zone': 2.5,
            'font_size': 8,
            'text_distance': 2.5,
            'background': 'white',
            'foreground': 'black',
            'write_text': True,
            'dpi': 200,
        }
        if options:
            default_options.update(options)

        # Normalise type name to python-barcode identifier
        type_map = {
            'Code128': 'code128',
            'EAN13':   'ean13',
            'EAN-13':  'ean13',
            'UPCA':    'upca',
            'UPC-A':   'upca',
            'Code39':  'code39',
        }
        bc_key = type_map.get(barcode_type, 'code128')

        try:
            writer = ImageWriter()
            bc = python_barcode.get(bc_key, barcode_value, writer=writer)
            buf = BytesIO()
            bc.write(buf, options=default_options)
            return buf.getvalue()
        except Exception:
            # Fallback: render as Code128 which accepts any ASCII string
            try:
                writer = ImageWriter()
                bc = python_barcode.get('code128', barcode_value, writer=writer)
                buf = BytesIO()
                bc.write(buf, options=default_options)
                return buf.getvalue()
            except Exception:
                return b''

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @staticmethod
    def detect_type(value: str) -> str:
        """Public accessor for type detection."""
        return _detect_barcode_type(value)
