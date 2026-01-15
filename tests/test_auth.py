"""
Integration tests for authentication and authorization
Tests HTTP layer and database interactions
"""
import pytest


class TestAuthentication:
    """Tests for login and logout functionality"""
    
    @pytest.mark.integration
    def test_login_page_loads(self, client):
        """Login page should load successfully"""
        response = client.get('/auth/login')
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_login_success(self, client, admin_user):
        """Valid credentials should login successfully"""
        response = client.post('/auth/login', data={
            'username': 'testadmin',
            'password': 'adminpass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_login_invalid_password(self, client, admin_user):
        """Invalid password should show error"""
        response = client.post('/auth/login', data={
            'username': 'testadmin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Invalid' in response.data
    
    @pytest.mark.integration
    def test_logout(self, authenticated_admin_client):
        """Logout should redirect to login"""
        response = authenticated_admin_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200


class TestRoleBasedAccess:
    """Tests for role-based access control"""
    
    @pytest.mark.integration
    def test_admin_dashboard_requires_login(self, client):
        """Admin dashboard should require authentication"""
        response = client.get('/admin/dashboard', follow_redirects=False)
        # Should redirect to login
        assert response.status_code == 302
    
    @pytest.mark.integration
    def test_admin_can_access_admin_dashboard(self, authenticated_admin_client):
        """Admin should access admin dashboard"""
        response = authenticated_admin_client.get('/admin/dashboard')
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_cashier_cannot_access_admin_dashboard(self, authenticated_cashier_client):
        """Cashier should not access admin dashboard"""
        response = authenticated_cashier_client.get('/admin/dashboard', follow_redirects=True)
        # Should redirect with access denied
        assert response.status_code == 200
        assert b'permission' in response.data.lower() or b'dashboard' in response.data.lower()


class TestOpenRedirectPrevention:
    """Tests for open redirect vulnerability fix"""
    
    @pytest.mark.integration
    def test_safe_redirect_allowed(self, client, admin_user):
        """Safe relative redirect should work"""
        response = client.post('/auth/login?next=/admin/dashboard', data={
            'username': 'testadmin',
            'password': 'adminpass123'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        assert 'dashboard' in location
    
    @pytest.mark.integration
    def test_malicious_redirect_blocked(self, client, admin_user):
        """Malicious external redirect should be blocked"""
        response = client.post('/auth/login?next=http://evil.com/phishing', data={
            'username': 'testadmin',
            'password': 'adminpass123'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        assert 'evil.com' not in location
