from flask import Flask, request, jsonify
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Entry
from utils import calculate_ideal_weight
import secrets


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
CORS(app)




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


@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.reset_token = secrets.token_urlsafe(32)
    db.session.commit()
    # Simulate sending email
    print(f"Password reset link: https://yourapp.com/reset?token={user.reset_token}")

    return jsonify({'message': 'Reset link sent to your email'})



@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    token = data.get('token')
    new_password = data.get('new_password')

    user = User.query.filter_by(reset_token=token).first()

    if not user:
        return jsonify({'error': 'Invalid token'}), 400

    user.set_password(new_password)
    user.reset_token = None
    db.session.commit()
    return jsonify({'message': 'Password has been reset'})





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
