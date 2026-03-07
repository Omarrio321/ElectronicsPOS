"""Add dual-currency support (USD + SLSH)

Adds payment_currency, exchange_rate_used, amount_in_usd to payment table.
Adds exchange_rate_at_sale to sale table.
Adds refund_currency to return_transaction table.

Revision ID: a1b2c3d4e5f6
Revises: d24fff74d40a
Create Date: 2026-03-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'd24fff74d40a'
branch_labels = None
depends_on = None


def upgrade():
    # --- payment table: add currency + exchange-rate columns ---
    # payment_currency: ENUM, NOT NULL, default 'USD' — all legacy rows become USD
    op.execute(
        "ALTER TABLE payment "
        "ADD COLUMN payment_currency ENUM('USD','SLSH') NOT NULL DEFAULT 'USD'"
    )

    # exchange_rate_used: 1 USD = X SLSH; legacy rows set to 1.0 (no conversion needed)
    op.execute(
        "ALTER TABLE payment "
        "ADD COLUMN exchange_rate_used DECIMAL(12,6) NOT NULL DEFAULT 1.000000"
    )

    # amount_in_usd: pre-populate existing rows with their amount (all were USD)
    op.execute(
        "ALTER TABLE payment "
        "ADD COLUMN amount_in_usd DECIMAL(12,2) NULL"
    )
    op.execute(
        "UPDATE payment SET amount_in_usd = amount"
    )

    # --- sale table: add exchange rate snapshot ---
    op.execute(
        "ALTER TABLE sale "
        "ADD COLUMN exchange_rate_at_sale DECIMAL(12,6) NULL"
    )

    # --- return_transaction table: add refund currency ---
    op.execute(
        "ALTER TABLE return_transaction "
        "ADD COLUMN refund_currency ENUM('USD','SLSH') NULL DEFAULT 'USD'"
    )
    # Set refund_currency = 'USD' where a refund method is set (all legacy refunds were USD)
    op.execute(
        "UPDATE return_transaction SET refund_currency = 'USD' WHERE refund_method IS NOT NULL"
    )


def downgrade():
    op.execute("ALTER TABLE return_transaction DROP COLUMN refund_currency")
    op.execute("ALTER TABLE sale DROP COLUMN exchange_rate_at_sale")
    op.execute("ALTER TABLE payment DROP COLUMN amount_in_usd")
    op.execute("ALTER TABLE payment DROP COLUMN exchange_rate_used")
    op.execute("ALTER TABLE payment DROP COLUMN payment_currency")
