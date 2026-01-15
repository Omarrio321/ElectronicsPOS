from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, DecimalField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, NumberRange, Optional
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Register')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        # Populate role choices here, not at import time
        from app.models import Role
        self.role_id.choices = [(role.id, role.name) for role in Role.query.all()]

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('New Password (leave blank to keep current)', validators=[Optional()])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        # Populate role choices here, not at import time
        from app.models import Role
        self.role_id.choices = [(role.id, role.name) for role in Role.query.all()]

class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Save')

class ProductForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[Optional()])
    sku = StringField('SKU', validators=[DataRequired()])
    barcode = StringField('Barcode', validators=[Optional()])
    description = TextAreaField('Description')
    cost_price = DecimalField('Cost Price', validators=[DataRequired(), NumberRange(min=0)])
    selling_price = DecimalField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    quantity = IntegerField('Quantity in Stock', validators=[DataRequired(), NumberRange(min=0)])
    low_stock_threshold = IntegerField('Low Stock Threshold', validators=[Optional(), NumberRange(min=0)])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save')

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        # Populate category choices here, not at import time
        from app.models import Category
        self.category_id.choices = [(0, '-- No Category --')] + [(category.id, category.name) for category in Category.query.all()]

class SystemSettingsForm(FlaskForm):
    tax_rate = DecimalField('Tax Rate', validators=[DataRequired(), NumberRange(min=0, max=1)])
    submit = SubmitField('Save Settings')

class ReportForm(FlaskForm):
    type = SelectField('Report Type', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])
    submit = SubmitField('Generate Report')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('New Password', validators=[Optional()])
    password_confirm = PasswordField('Confirm New Password', validators=[EqualTo('password')])
    submit = SubmitField('Update Profile')