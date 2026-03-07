"""
Currency conversion and validation utilities for dual-currency (USD / SLSH) support.

Design rules:
  - USD is the base/accounting currency; all totals are stored in USD.
  - SLSH is the secondary currency for cash/mobile payments.
  - Card payments are restricted to USD only.
  - Exchange rate is 1 USD = X SLSH (stored in SystemSetting 'exchange_rate_usd_slsh').
  - The rate at transaction time is snapshotted on each Payment and on the Sale.
"""

from decimal import Decimal, ROUND_HALF_UP
from app.models import PaymentMethod, PaymentCurrency

# Methods that are restricted to USD only
_USD_ONLY_METHODS = {PaymentMethod.CARD}


def is_valid_payment_combination(method: PaymentMethod, currency: PaymentCurrency) -> bool:
    """Return True if the method + currency combination is permitted."""
    if method in _USD_ONLY_METHODS and currency == PaymentCurrency.SLSH:
        return False
    return True


def get_current_exchange_rate() -> Decimal:
    """
    Return the current 1-USD-to-SLSH exchange rate from SystemSetting.
    Defaults to 1000 if not configured.
    """
    from app.models import SystemSetting
    try:
        raw = SystemSetting.get('exchange_rate_usd_slsh', '1000')
        rate = Decimal(str(raw))
        if rate <= 0:
            raise ValueError("Rate must be positive")
        return rate
    except Exception:
        return Decimal('1000')


def to_usd(amount: Decimal, currency: PaymentCurrency, rate: Decimal) -> Decimal:
    """
    Convert an amount denominated in `currency` to its USD equivalent.

    Args:
        amount: The payment amount in its original currency.
        currency: PaymentCurrency.USD or PaymentCurrency.SLSH.
        rate: The exchange rate (1 USD = rate SLSH) at the time of the transaction.

    Returns:
        USD-equivalent amount, rounded to 2 decimal places.
    """
    if currency == PaymentCurrency.USD:
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if currency == PaymentCurrency.SLSH:
        if rate <= 0:
            raise ValueError("Exchange rate must be positive")
        return (amount / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    raise ValueError(f"Unsupported currency: {currency}")


def to_slsh(amount_usd: Decimal, rate: Decimal) -> Decimal:
    """
    Convert a USD amount to its SLSH equivalent for display purposes.
    Rounded to the nearest whole SLSH (no cents in SLSH).
    """
    return (amount_usd * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
