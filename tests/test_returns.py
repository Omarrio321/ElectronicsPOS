"""
Tests for Return/Refund Management and Void Sale functionality.
"""
import pytest
from decimal import Decimal
from app.models import db, Sale, SaleItem, Product, Payment, PaymentMethod, SaleStatus, InvoiceStatus, ReturnTransaction, ReturnItem, ReturnType, ReturnStatus, VoidTransaction, AuditLog

@pytest.fixture
def test_sale(db_session, cashier_user, product):
    """Create a standard completed sale for testing returns/voids"""
    # 2 items at 799.99 each
    item_subtotal = product.selling_price * 2  # 1599.98
    tax_rate = Decimal('0.08')
    tax_amount = (item_subtotal * tax_rate).quantize(Decimal('0.01'))  # 127.9984 -> 128.00
    grand_total = item_subtotal + tax_amount  # 1727.98

    sale = Sale(
        invoice_no='INV-TEST-001',
        user_id=cashier_user.id,
        subtotal=item_subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        discount=Decimal('0.00'),
        grand_total=grand_total,
        amount_paid=grand_total,
        amount_due=Decimal('0.00'),
        change_given=Decimal('0.00'),
        payment_method=PaymentMethod.CASH,
        sale_status=SaleStatus.COMPLETED,
        invoice_status=InvoiceStatus.PAID
    )
    db_session.add(sale)
    db_session.flush()

    sale_item = SaleItem(
        sale_id=sale.id,
        product_id=product.id,
        product_name=product.name,
        product_sku=product.sku,
        quantity_sold=2,
        unit_price_at_time=product.selling_price,
        total_price=item_subtotal
    )
    db_session.add(sale_item)

    payment = Payment(
        sale_id=sale.id,
        amount=grand_total,
        payment_method=PaymentMethod.CASH,
        created_by=cashier_user.id
    )
    db_session.add(payment)

    # Deduct stock as it would happen in real sale
    product.quantity_in_stock -= 2

    db_session.commit()
    return sale


def test_get_returnable_qty(app, db_session, test_sale):
    """Test get_returnable_qty helper method"""
    sale = db_session.merge(test_sale)
    item = sale.sale_items[0]
    
    assert sale.get_returnable_qty(item.id) == 2
    
    # Add a partial return
    ret = ReturnTransaction(
        return_no='RTN-TEST-1',
        sale_id=sale.id,
        return_type=ReturnType.RETURN_AND_REFUND,
        subtotal=item.unit_price_at_time,
        tax_amount=Decimal('64.00') / 2,
        discount_amount=0,
        refund_total=Decimal('863.99') / 2,
        reason='Test reason',
        processed_by=sale.user_id
    )
    db_session.add(ret)
    db_session.flush()
    
    ret_item = ReturnItem(
        return_id=ret.id,
        sale_item_id=item.id,
        product_id=item.product_id,
        quantity_returned=1,
        unit_price_at_sale=item.unit_price_at_time,
        total_price=item.unit_price_at_time
    )
    db_session.add(ret_item)
    db_session.commit()
    
    # Should now be 1
    assert sale.get_returnable_qty(item.id) == 1


def test_return_qty_cannot_exceed_sold(authenticated_cashier_client, test_sale, db_session):
    """Test returning more than the original sold quantity"""
    sale_item_id = test_sale.sale_items[0].id
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 3}],  # Original sold was 2
        'reason': 'Test',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    data = response.get_json()
    assert response.status_code == 400
    assert data['success'] is False
    assert 'exceeds returnable' in data['message']


def test_return_restores_stock(authenticated_cashier_client, test_sale, db_session):
    """Test that a valid return restores product stock"""
    initial_stock = Product.query.get(test_sale.sale_items[0].product_id).quantity_in_stock
    sale_item_id = test_sale.sale_items[0].id
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 1}],
        'reason': 'Defective',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Stock should increase by 1
    product = Product.query.get(test_sale.sale_items[0].product_id)
    assert product.quantity_in_stock == initial_stock + 1


def test_full_return_marks_refunded(authenticated_cashier_client, test_sale, db_session):
    """Test that returning all items marks sale as REFUNDED"""
    sale_item_id = test_sale.sale_items[0].id
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 2}],
        'reason': 'Changed mind',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    assert response.status_code == 200
    
    db_session.expire_all()
    sale = Sale.query.get(test_sale.id)
    assert sale.sale_status == SaleStatus.REFUNDED


def test_partial_return_marks_partially_returned(authenticated_cashier_client, test_sale, db_session):
    """Test that returning some items marks sale as PARTIALLY_RETURNED"""
    sale_item_id = test_sale.sale_items[0].id
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 1}],
        'reason': 'Wrong item',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    assert response.status_code == 200
    
    db_session.expire_all()
    sale = Sale.query.get(test_sale.id)
    assert sale.sale_status == SaleStatus.PARTIALLY_RETURNED


def test_refund_total_correct_with_tax(authenticated_cashier_client, test_sale, db_session):
    """Test that the refunded amount correctly includes proportional tax"""
    sale_item_id = test_sale.sale_items[0].id
    
    # Returning 1 out of 2 items (half the sale)
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 1}],
        'reason': 'Defective',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    data = response.get_json()
    assert response.status_code == 200
    
    # Returning 1 of 2 items: 799.99 * 1.08 = 863.9892 ≈ 863.99
    assert abs(data['refund_total'] - 863.99) < 0.01


def test_return_creates_audit_record(authenticated_cashier_client, test_sale, db_session):
    """Test that a return transaction creates an AuditLog entry"""
    sale_item_id = test_sale.sale_items[0].id
    
    authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': sale_item_id, 'quantity': 1}],
        'reason': 'Defective',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    db_session.expire_all()
    audit_log = AuditLog.query.filter_by(action='RETURN_PROCESSED').first()
    assert audit_log is not None
    assert audit_log.details['sale_id'] == test_sale.id


def test_cannot_return_voided_sale(authenticated_cashier_client, test_sale, db_session):
    """Test that items cannot be returned from a voided sale"""
    test_sale.sale_status = SaleStatus.VOIDED
    db_session.commit()
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/return', json={
        'items': [{'sale_item_id': test_sale.sale_items[0].id, 'quantity': 1}],
        'reason': 'Test',
        'return_type': 'RETURN_AND_REFUND',
        'refund_method': 'Cash'
    })
    
    assert response.status_code == 400
    assert 'voided sale' in response.get_json()['message'].lower()


# --- VOID TESTS ---

def test_void_blocks_paid_sale_without_manager(authenticated_cashier_client, test_sale, db_session):
    """Test that a cashier cannot void a paid sale - it should be blocked and prompt for refund flow"""
    # Cashier voiding a paid sale is blocked entirely because we prefer the refund flow
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/void', json={
        'reason': 'Mistake'
    })
    
    assert response.status_code == 400
    assert 'existing payments' in response.get_json()['message'].lower()


def test_void_unpaid_sale_restores_stock(authenticated_admin_client, test_sale, db_session):
    """Test voiding an unpaid/pending sale restores stock and voids it"""
    # Make sale unpaid
    test_sale.invoice_status = InvoiceStatus.UNPAID
    test_sale.amount_paid = Decimal('0')
    test_sale.amount_due = test_sale.grand_total
    for p in test_sale.payments:
        db_session.delete(p)
    db_session.commit()

    initial_stock = Product.query.get(test_sale.sale_items[0].product_id).quantity_in_stock

    response = authenticated_admin_client.post(f'/sales/{test_sale.id}/void', json={
        'reason': 'Customer left'
    })
    
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    db_session.expire_all()
    sale = Sale.query.get(test_sale.id)
    assert sale.sale_status == SaleStatus.VOIDED
    assert sale.invoice_status == InvoiceStatus.VOID
    
    # Stock should be restored
    product = Product.query.get(test_sale.sale_items[0].product_id)
    assert product.quantity_in_stock == initial_stock + 2


def test_cannot_void_already_voided(authenticated_cashier_client, test_sale, db_session):
    """Test double voiding is prevented"""
    test_sale.sale_status = SaleStatus.VOIDED
    db_session.commit()
    
    response = authenticated_cashier_client.post(f'/sales/{test_sale.id}/void', json={
        'reason': 'Mistake'
    })
    
    assert response.status_code == 400
    assert 'already voided' in response.get_json()['message'].lower()


def test_void_creates_audit_record(authenticated_admin_client, test_sale, db_session):
    """Test voiding a sale creates an AuditLog record"""
    # Make sale unpaid
    test_sale.invoice_status = InvoiceStatus.UNPAID
    test_sale.amount_paid = Decimal('0')
    for p in test_sale.payments:
        db_session.delete(p)
    db_session.commit()

    authenticated_admin_client.post(f'/sales/{test_sale.id}/void', json={
        'reason': 'Mistake'
    })
    
    db_session.expire_all()
    audit_log = AuditLog.query.filter_by(action='SALE_VOIDED').first()
    assert audit_log is not None
    assert audit_log.details['sale_id'] == test_sale.id
