from flask import Blueprint, jsonify, request
from app.models import Product, Category
from app import db
from sqlalchemy import or_

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/categories')
def get_categories():
    categories = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in categories])

@api_bp.route('/products')
def get_products():
    category_id = request.args.get('category_id')
    search = request.args.get('search')
    
    query = Product.query.filter(Product.is_active == True)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
        
    if search:
        query = query.filter(or_(
            Product.name.contains(search),
            Product.sku.contains(search),
            Product.barcode.contains(search)
        ))
        
    products = query.order_by(Product.name).limit(50).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': float(p.selling_price),
        'sku': p.sku,
        'quantity': p.quantity_in_stock,
        'category_id': p.category_id
    } for p in products])
