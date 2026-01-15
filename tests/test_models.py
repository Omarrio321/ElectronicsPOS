"""
Unit tests for model logic
Tests core business logic without HTTP layer
"""
import pytest
from decimal import Decimal
from app.models import Product, Sale, SaleItem, User, PaymentMethod


class TestProductModel:
    """Tests for Product model business logic"""
    
    @pytest.mark.unit
    def test_is_low_stock_below_threshold(self, db_session, product):
        """Product below threshold should report low stock"""
        product.quantity_in_stock = 3
        product.low_stock_threshold = 5
        db_session.commit()
        
        assert product.is_low_stock() is True
    
    @pytest.mark.unit
    def test_is_low_stock_above_threshold(self, db_session, product):
        """Product above threshold should not report low stock"""
        product.quantity_in_stock = 10
        product.low_stock_threshold = 5
        db_session.commit()
        
        assert product.is_low_stock() is False
    
    @pytest.mark.unit
    def test_is_low_stock_at_threshold(self, db_session, product):
        """Product at exactly threshold should report low stock"""
        product.quantity_in_stock = 5
        product.low_stock_threshold = 5
        db_session.commit()
        
        assert product.is_low_stock() is True
    
    @pytest.mark.unit
    def test_update_stock_positive(self, db_session, product):
        """Stock should increase with positive quantity"""
        initial_stock = product.quantity_in_stock
        product.update_stock(5)
        db_session.commit()
        
        assert product.quantity_in_stock == initial_stock + 5
    
    @pytest.mark.unit
    def test_update_stock_negative(self, db_session, product):
        """Stock should decrease with negative quantity"""
        product.quantity_in_stock = 10
        db_session.commit()
        product.update_stock(-3)
        db_session.commit()
        
        assert product.quantity_in_stock == 7
    
    @pytest.mark.unit
    def test_update_stock_insufficient_raises_error(self, db_session, product):
        """Should raise ValueError when stock would go negative"""
        product.quantity_in_stock = 5
        db_session.commit()
        
        with pytest.raises(ValueError, match="Insufficient stock"):
            product.update_stock(-10)


class TestSaleCalculations:
    """Tests for Sale model calculation logic"""
    
    @pytest.mark.unit
    def test_calculate_totals(self, db_session, admin_user, product):
        """Sale totals should be calculated correctly"""
        # Create sale
        sale = Sale(
            user_id=admin_user.id,
            subtotal=Decimal('0'),
            tax_rate=Decimal('0.08'),
            tax_amount=Decimal('0'),
            discount=Decimal('0'),
            grand_total=Decimal('0'),
            payment_method=PaymentMethod.CASH,
            amount_paid=Decimal('200'),
            change_given=Decimal('0')
        )
        db_session.add(sale)
        db_session.flush()
        
        # Add sale items
        item1 = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity_sold=2,
            unit_price_at_time=Decimal('50.00'),
            total_price=Decimal('100.00')
        )
        db_session.add(item1)
        db_session.flush()
        
        # Calculate totals
        sale.calculate_totals()
        
        assert sale.subtotal == Decimal('100.00')
        assert sale.tax_amount == Decimal('8.00')  # 100 * 0.08
        assert sale.grand_total == Decimal('108.00')
    
    @pytest.mark.unit
    def test_calculate_totals_with_discount(self, db_session, admin_user, product):
        """Sale totals should apply discount correctly"""
        sale = Sale(
            user_id=admin_user.id,
            subtotal=Decimal('0'),
            tax_rate=Decimal('0.08'),
            tax_amount=Decimal('0'),
            discount=Decimal('10.00'),
            grand_total=Decimal('0'),
            payment_method=PaymentMethod.CASH,
            amount_paid=Decimal('200'),
            change_given=Decimal('0')
        )
        db_session.add(sale)
        db_session.flush()
        
        item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity_sold=2,
            unit_price_at_time=Decimal('50.00'),
            total_price=Decimal('100.00')
        )
        db_session.add(item)
        db_session.flush()
        
        sale.calculate_totals()
        
        # Grand total = subtotal + tax - discount = 100 + 8 - 10 = 98
        assert sale.grand_total == Decimal('98.00')


class TestUserModel:
    """Tests for User model authentication logic"""
    
    @pytest.mark.unit
    def test_check_password_correct(self, admin_user):
        """Correct password should return True"""
        assert admin_user.check_password('adminpass123') is True
    
    @pytest.mark.unit
    def test_check_password_incorrect(self, admin_user):
        """Incorrect password should return False"""
        assert admin_user.check_password('wrongpassword') is False
    
    @pytest.mark.unit
    def test_has_role_correct(self, admin_user):
        """User should have their assigned role"""
        assert admin_user.has_role('Admin') is True
    
    @pytest.mark.unit
    def test_has_role_incorrect(self, admin_user):
        """User should not have unassigned roles"""
        assert admin_user.has_role('Cashier') is False
