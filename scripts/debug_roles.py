from app import create_app, db
from app.models import User, Role
from dotenv import load_dotenv
import os

load_dotenv()

app = create_app()

with app.app_context():
    print("-" * 50)
    print("DEBUGGING USER ROLES")
    print("-" * 50)
    
    # List all Roles
    roles = Role.query.all()
    print(f"Available Roles in DB: {[r.name for r in roles]}")
    
    # List all Users and their Roles
    users = User.query.all()
    for u in users:
        role_name = u.role.name if u.role else "NO ROLE"
        print(f"User: '{u.username}' | Role: '{role_name}' | ID: {u.id}")
        
    # Test has_role logic for 'admin'
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        print("-" * 50)
        print(f"Testing permissions for '{admin_user.username}':")
        print(f"Has 'Admin'? {admin_user.has_role('Admin')}")
        print(f"Has 'Manager'? {admin_user.has_role('Manager')}")
        print(f"Has 'Cashier'? {admin_user.has_role('Cashier')}")
        
        # Check specific decorator strings
        required = ['Cashier', 'Manager', 'Admin']
        has_permission = any(admin_user.has_role(r) for r in required)
        print(f"Access to POS (requires one of {required}): {has_permission}")
    else:
        print("ERROR: User 'admin' not found!")
    print("-" * 50)
