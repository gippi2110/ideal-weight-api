import os
from flask import Flask, request, jsonify, url_for
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Entry
from utils import calculate_ideal_weight
import secrets
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Example: Gmail SMTP
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # Set in environment
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Set in environment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')  # Required for serializer
db.init_app(app)
CORS(app)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    username = data.get('username')
    user = User(email=data['email'], username=username)
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Registered successfully'})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        return jsonify({'message': 'Login successful', 'user_id': user.id})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Email not found'}), 404

    # Generate reset token
    token = serializer.dumps(user.email, salt='password-reset-salt')
    user.reset_token = token
    user.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    # Send reset email
    reset_link = url_for('reset_password', token=token, _external=True)
    msg = Message('Password Reset Request',
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[user.email])
    msg.body = f'To reset your password, click the link: {reset_link}\nThis link expires in 1 hour.'
    try:
        mail.send(msg)
        return jsonify({'message': 'Password reset link sent to your email'})
    except Exception as e:
        return jsonify({'error': 'Failed to send email'}), 500




@app.route('/admin/register', methods=['POST'])
def admin_register():
    data = request.json
    if Admin.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    if Admin.query.filter_by(admin_id=data['admin_id']).first():
        return jsonify({'error': 'Admin ID already exists'}), 409

    admin = Admin(
        email=data['email'],
        username=data['username'],
        admin_id=data['admin_id']
    )
    admin.set_password(data['password'])
    db.session.add(admin)
    db.session.commit()

    return jsonify({'message': 'Admin registered successfully', 'admin_id': admin.admin_id})


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    admin = Admin.query.filter_by(email=data['email']).first()
    if admin and admin.check_password(data['password']):
        return jsonify({'message': 'Login successful', 'admin_id': admin.admin_id, 'username': admin.username})
    return jsonify({'error': 'Invalid credentials'}), 401

# app.py

from datetime import datetime

@app.route('/admin/overview', methods=['GET'])
def admin_overview():
    admin_id = request.args.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Admin ID is required'}), 400

    # Get users assigned to this admin
    users = User.query.filter_by(admin_id=admin_id).all()
    user_ids = [user.id for user in users]

    # Query all entries by those users
    total_entries = Entry.query.filter(Entry.user_id.in_(user_ids)).count()

    # Today's date filter
    today = datetime.now().date()
    today_entries = Entry.query.filter(
        Entry.user_id.in_(user_ids),
        db.func.date(Entry.timestamp) == today
    ).count()

    return jsonify({
        'user_count': len(users),
        'total_entries': total_entries,
        'today_entries': today_entries
    })





@app.route('/reset_password/<token>', methods=['POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiration
    except:
        return jsonify({'error': 'Invalid or expired reset link'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or user.reset_token != token or user.reset_token_expiration < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired reset link'}), 400

    data = request.json
    new_password = data.get('password')
    if not new_password:
        return jsonify({'error': 'Password is required'}), 400

    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expiration = None
    db.session.commit()
    return jsonify({'message': 'Password reset successfully'})

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    user_id = data['user_id']
    load = data['load']
    temperature = data['temperature']
    pressure = data['pressure']
    hydraulic = data['hydraulic']

    ideal_weight = calculate_ideal_weight(load, temperature, pressure, hydraulic)

    entry = Entry(
        user_id=user_id,
        load=load,
        temperature=temperature,
        pressure=pressure,
        hydraulic=hydraulic,
        ideal_weight=ideal_weight
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'ideal_weight': ideal_weight})

@app.route('/overview', methods=['GET'])
def overview():
    user_id = request.args.get('user_id')
    entries = Entry.query.filter_by(user_id=user_id).all()
    if not entries:
        return jsonify({'total': 0, 'avg_load': 0, 'avg_ideal_weight': 0})

    total = len(entries)
    avg_load = sum(e.load for e in entries) / total
    avg_ideal_weight = sum(e.ideal_weight for e in entries) / total
    return jsonify({
        'total': total,
        'avg_load': round(avg_load, 2),
        'avg_ideal_weight': round(avg_ideal_weight, 2)
    })

@app.route('/history', methods=['GET'])
def history():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    entries = Entry.query.filter_by(user_id=user_id).order_by(Entry.timestamp.desc()).all()

    result = [{
        "timestamp": entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        "load": entry.load,
        "temperature": entry.temperature,
        "pressure": entry.pressure,
        "hydraulic": entry.hydraulic,
        "ideal_weight": entry.ideal_weight
    } for entry in entries]

    return jsonify(result)

@app.route('/analytics', methods=['GET'])
def analytics():
    user_id = request.args.get('user_id')

    # Query all entries for the user
    entries = Entry.query.filter_by(user_id=user_id).order_by(Entry.timestamp).all()

    # Structure the response data
    data = {
        'load_vs_weight': [[entry.load, entry.ideal_weight] for entry in entries],
        'temp_vs_weight': [[entry.temperature, entry.ideal_weight] for entry in entries],
        'pressure_vs_weight': [[entry.pressure, entry.ideal_weight] for entry in entries],
        'hydraulic_vs_weight': [[entry.hydraulic, entry.ideal_weight] for entry in entries]
    }

    return jsonify(data)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()
