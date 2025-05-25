from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Entry
from utils import calculate_ideal_weight

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

    user = User(email=data['email'])
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
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, load, temperature, pressure, hydraulic, ideal_weight
        FROM weight_history
        WHERE user_id=?
        ORDER BY timestamp DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    result = [
        {
            "timestamp": row[0],
            "load": row[1],
            "temperature": row[2],
            "pressure": row[3],
            "hydraulic": row[4],
            "ideal_weight": row[5]
        }
        for row in rows
    ]

    return jsonify(result)



@app.route('/analytics', methods=['GET'])
def analytics():
    user_id = request.args.get('user_id')
    entries = Entry.query.filter_by(user_id=user_id).all()
    return jsonify({
        'temp_vs_weight': [(e.temperature, e.ideal_weight) for e in entries],
        'pressure_vs_weight': [(e.pressure, e.ideal_weight) for e in entries],
        'hydraulic_vs_weight': [(e.hydraulic, e.ideal_weight) for e in entries]
    })


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()
