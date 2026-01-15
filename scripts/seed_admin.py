import os
from app import create_app, db
from app.models import User, Role
from dotenv import load_dotenv

load_dotenv()

app = create_app()

with app.app_context():
    # check if admin exists
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        print("Error: Admin role not found. Run init-db first.")
        exit(1)
        
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        print("Admin user already exists.")
    else:
        password = os.environ.get('ADMIN_PASSWORD')
        if not password:
            print("ADMIN_PASSWORD not in environment, using default 'admin123'")
            password = 'admin123'
            
        print(f"Creating admin user with password: {password}")
        admin = User(
            username='admin',
            email='admin@example.com',
            role=admin_role,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
