"""Add barcode subsystem: barcode_type, barcode_source on product, barcode_sequence table

Adds barcode_type and barcode_source columns to the product table.
Creates barcode_sequence table for concurrency-safe internal barcode generation.
Backfills barcode_source='manual' for existing products that already have a barcode.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # --- product table: add barcode metadata columns ---
    op.execute(
        "ALTER TABLE product "
        "ADD COLUMN barcode_type VARCHAR(20) NULL "
        "COMMENT 'Code128, EAN13, UPCA'"
    )
    op.execute(
        "ALTER TABLE product "
        "ADD COLUMN barcode_source VARCHAR(20) NULL "
        "COMMENT 'generated, manual, supplier'"
    )

    # Backfill: existing products that already have a barcode value → mark as manual
    op.execute(
        "UPDATE product SET barcode_type='Code128', barcode_source='manual' "
        "WHERE barcode IS NOT NULL AND barcode != ''"
    )

    # --- barcode_sequence table: atomic counter for generated barcodes ---
    op.execute("""
        CREATE TABLE barcode_sequence (
            id INT NOT NULL AUTO_INCREMENT,
            prefix VARCHAR(20) NOT NULL,
            last_sequence INT NOT NULL DEFAULT 0,
            updated_at DATETIME NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uq_barcode_sequence_prefix (prefix)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Seed the default prefix row so the first generation doesn't need an INSERT
    op.execute(
        "INSERT INTO barcode_sequence (prefix, last_sequence, updated_at) "
        "VALUES ('EP', 0, NOW())"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS barcode_sequence")
    op.execute("ALTER TABLE product DROP COLUMN barcode_source")
    op.execute("ALTER TABLE product DROP COLUMN barcode_type")
