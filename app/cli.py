import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Role

@click.group()
def cli():
    """Management commands for the POS application."""
    pass

@cli.command()
@with_appcontext
def create_admin():
    """Create an admin user."""
    username = click.prompt('Username')
    email = click.prompt('Email')
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        click.echo(f'User {username} already exists!')
        return
    
    if User.query.filter_by(email=email).first():
        click.echo(f'Email {email} already exists!')
        return
    
    # Get or create admin role
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_role = Role(name='Admin', description='Full system access')
        db.session.add(admin_role)
    
    # Create admin user
    admin_user = User(
        username=username,
        email=email,
        role_id=admin_role.id,
        is_active=True
    )
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()
    
    click.echo(f'Admin user {username} created successfully!')

@cli.command()
@with_appcontext
def reset_password():
    """Reset a user's password."""
    username = click.prompt('Username')
    password = click.prompt('New password', hide_input=True, confirmation_prompt=True)
    
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f'User {username} not found!')
        return
    
    user.set_password(password)
    db.session.commit()
    
    click.echo(f'Password for {username} updated successfully!')

@cli.command()
@with_appcontext
def list_users():
    """List all users."""
    users = User.query.all()
    
    if not users:
        click.echo('No users found!')
        return
    
    click.echo('ID\tUsername\tEmail\tRole\tActive')
    click.echo('-' * 50)
    
    for user in users:
        click.echo(f'{user.id}\t{user.username}\t{user.email}\t{user.role.name}\t{user.is_active}')

@cli.command()
@with_appcontext
def init_db():
    """Initialize the database with default data."""
    click.echo('Creating database tables...')
    db.create_all()
    
    click.echo('Creating default roles...')
    roles = [
        {'name': 'Admin', 'description': 'Full system access'},
        {'name': 'Manager', 'description': 'Manage products and view reports'},
        {'name': 'Cashier', 'description': 'Process sales'}
    ]
    
    for role_data in roles:
        role = Role.query.filter_by(name=role_data['name']).first()
        if not role:
            role = Role(**role_data)
            db.session.add(role)
    
    db.session.commit()
    click.echo('Database initialized successfully!')

@cli.command()
@with_appcontext
def seed_data():
    """Seed the database with sample data."""
    from app.models import Category, Product, SystemSetting
    
    click.echo('Creating sample categories...')
    categories = [
        {'name': 'Smartphones', 'description': 'Mobile phones and accessories'},
        {'name': 'Laptops', 'description': 'Notebook and desktop computers'},
        {'name': 'Tablets', 'description': 'Tablet computers and e-readers'},
        {'name': 'Accessories', 'description': 'Electronic accessories and peripherals'}
    ]
    
    for cat_data in categories:
        category = Category.query.filter_by(name=cat_data['name']).first()
        if not category:
            category = Category(**cat_data)
            db.session.add(category)
    
    db.session.commit()
    
    click.echo('Creating sample products...')
    products = [
        {
            'name': 'iPhone 13 Pro',
            'category_id': Category.query.filter_by(name='Smartphones').first().id,
            'sku': 'IPHONE13PRO-256',
            'barcode': '1234567890123',
            'description': 'iPhone 13 Pro with 256GB storage',
            'cost_price': 899.00,
            'selling_price': 1099.00,
            'quantity_in_stock': 50,
            'low_stock_threshold': 10
        },
        {
            'name': 'MacBook Pro 16"',
            'category_id': Category.query.filter_by(name='Laptops').first().id,
            'sku': 'MBP16-2021',
            'barcode': '1234567890124',
            'description': 'MacBook Pro 16" with M1 Pro chip',
            'cost_price': 2199.00,
            'selling_price': 2499.00,
            'quantity_in_stock': 20,
            'low_stock_threshold': 5
        }
    ]
    
    for prod_data in products:
        product = Product.query.filter_by(sku=prod_data['sku']).first()
        if not product:
            product = Product(**prod_data)
            db.session.add(product)
    
    db.session.commit()
    
    click.echo('Setting system defaults...')
    SystemSetting.set('tax_rate', '0.08', 'Default tax rate (8%)')
    
    click.echo('Sample data seeded successfully!')