"""
Integration tests for POS workflow
Tests cart operations and checkout process
"""
import pytest
import json


class TestPOSSearch:
    """Tests for product search functionality"""
    
    @pytest.mark.integration
    def test_search_products_by_name(self, authenticated_admin_client, product):
        """Should find products by name"""
        response = authenticated_admin_client.post('/search', data={
            'query': 'Test Laptop',
            'category_id': ''
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'products' in data
    
    @pytest.mark.integration
    def test_search_products_by_sku(self, authenticated_admin_client, product):
        """Should find products by SKU"""
        response = authenticated_admin_client.post('/search', data={
            'query': 'LAPTOP-001',
            'category_id': ''
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'products' in data


class TestCartOperations:
    """Tests for cart CRUD operations"""
    
    @pytest.mark.integration
    def test_add_to_cart(self, authenticated_admin_client, product):
        """Should add product to cart"""
        response = authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 1
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is True
        assert data.get('cart_count') == 1
    
    @pytest.mark.integration
    def test_add_to_cart_insufficient_stock(self, authenticated_admin_client, product):
        """Should reject when quantity exceeds stock"""
        response = authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 999
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is False
        assert 'stock' in data.get('message', '').lower()
    
    @pytest.mark.integration
    def test_update_cart_quantity(self, authenticated_admin_client, product):
        """Should update cart item quantity"""
        # First add to cart
        authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 1
        })
        
        # Update quantity
        response = authenticated_admin_client.post('/update_cart', data={
            'product_id': product.id,
            'quantity': 3
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is True
    
    @pytest.mark.integration
    def test_remove_from_cart(self, authenticated_admin_client, product):
        """Should remove product from cart"""
        # First add to cart
        authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 1
        })
        
        # Remove from cart
        response = authenticated_admin_client.post('/remove_from_cart', data={
            'product_id': product.id
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is True
        assert data.get('cart_count') == 0
    
    @pytest.mark.integration
    def test_clear_cart(self, authenticated_admin_client, product):
        """Should clear entire cart"""
        # Add items to cart
        authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 2
        })
        
        # Clear cart
        response = authenticated_admin_client.post('/clear_cart')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is True
        assert data.get('cart') == []


class TestCheckout:
    """Tests for checkout workflow"""
    
    @pytest.mark.integration
    def test_checkout_empty_cart_fails(self, authenticated_admin_client):
        """Checkout with empty cart should fail"""
        response = authenticated_admin_client.post('/checkout', data={
            'payment_method': 'CASH',
            'amount_paid': 100,
            'discount': 0
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is False
        assert 'empty' in data.get('message', '').lower()
    
    @pytest.mark.integration
    def test_checkout_success(self, authenticated_admin_client, db_session, product):
        """Successful checkout should create sale and update stock"""
        initial_stock = product.quantity_in_stock
        
        # Add to cart
        authenticated_admin_client.post('/add_to_cart', data={
            'product_id': product.id,
            'quantity': 2
        })
        
        # Checkout with sufficient payment
        total = float(product.selling_price) * 2 * 1.08  # Including tax
        response = authenticated_admin_client.post('/checkout', data={
            'payment_method': 'CASH',
            'amount_paid': total + 50,  # Extra for change
            'discount': 0
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') is True
        assert 'sale_id' in data
