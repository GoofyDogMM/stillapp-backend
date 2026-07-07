from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)
CORS(app)

# Database initialization
def init_db():
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 500,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Models table
    c.execute('''CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY,
        name TEXT,
        photo_urls TEXT,
        video_urls TEXT
    )''')
    
    # Transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT,
        model_name TEXT,
        content_type TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Check if models exist, if not create defaults
    c.execute('SELECT COUNT(*) FROM models')
    if c.fetchone()[0] == 0:
        models = [
            ('Whylollycry', '["https://telegra.ph/file/sample1.jpg","https://telegra.ph/file/sample2.jpg"]', '["https://telegra.ph/file/video1.mp4"]'),
            ('Аня мур', '["https://telegra.ph/file/sample3.jpg","https://telegra.ph/file/sample4.jpg"]', '["https://telegra.ph/file/video2.mp4"]'),
            ('Tenlikova', '["https://telegra.ph/file/sample5.jpg","https://telegra.ph/file/sample6.jpg"]', '["https://telegra.ph/file/video3.mp4"]'),
        ]
        c.executemany('INSERT INTO models (name, photo_urls, video_urls) VALUES (?, ?, ?)', models)
    
    conn.commit()
    conn.close()

init_db()

# Get or create user
def get_user(user_id):
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result is None:
        c.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, 500))
        conn.commit()
        balance = 500
    else:
        balance = result[0]
    
    conn.close()
    return balance

# Update user balance
def update_balance(user_id, amount, tx_type, model_name=None, content_type=None):
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    
    current_balance = get_user(user_id)
    new_balance = current_balance + amount
    
    if new_balance < 0:
        conn.close()
        return False
    
    c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    c.execute('INSERT INTO transactions (user_id, amount, type, model_name, content_type) VALUES (?, ?, ?, ?, ?)',
              (user_id, amount, tx_type, model_name, content_type))
    
    conn.commit()
    conn.close()
    return True

# API Routes

@app.route('/api/user/<int:user_id>/balance', methods=['GET'])
def get_balance(user_id):
    balance = get_user(user_id)
    return jsonify({'balance': balance})

@app.route('/api/user/<int:user_id>/balance', methods=['POST'])
def set_balance(user_id):
    data = request.json
    amount = data.get('amount', 0)
    
    if amount < 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    update_balance(user_id, amount, 'add_promo', None, None)
    return jsonify({'balance': get_user(user_id)})

@app.route('/api/purchase', methods=['POST'])
def purchase():
    data = request.json
    user_id = data.get('user_id')
    cost = data.get('cost')
    model_name = data.get('model')
    content_type = data.get('type')  # 'photo' or 'video'
    
    if not user_id or not cost:
        return jsonify({'error': 'Missing parameters'}), 400
    
    success = update_balance(user_id, -cost, 'purchase', model_name, content_type)
    
    if success:
        return jsonify({
            'success': True,
            'balance': get_user(user_id),
            'message': f'Successfully purchased {content_type} from {model_name}'
        })
    else:
        return jsonify({'error': 'Insufficient funds'}), 400

@app.route('/api/models', methods=['GET'])
def get_models():
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    c.execute('SELECT name, photo_urls, video_urls FROM models')
    models = c.fetchall()
    conn.close()
    
    result = []
    for name, photo_urls, video_urls in models:
        result.append({
            'name': name,
            'photos': json.loads(photo_urls),
            'videos': json.loads(video_urls)
        })
    
    return jsonify(result)

@app.route('/api/admin/upload', methods=['POST'])
def admin_upload():
    admin_key = request.headers.get('X-Admin-Key')
    
    # Simple admin key check
    if admin_key != 'zxc123qwE+':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    model_name = data.get('model')
    url = data.get('url')
    content_type = data.get('type')  # 'photo' or 'video'
    
    if not all([model_name, url, content_type]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    
    if content_type == 'photo':
        c.execute('SELECT photo_urls FROM models WHERE name = ?', (model_name,))
    else:
        c.execute('SELECT video_urls FROM models WHERE name = ?', (model_name,))
    
    result = c.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Model not found'}), 404
    
    urls = json.loads(result[0])
    urls.append(url)
    
    if content_type == 'photo':
        c.execute('UPDATE models SET photo_urls = ? WHERE name = ?', (json.dumps(urls), model_name))
    else:
        c.execute('UPDATE models SET video_urls = ? WHERE name = ?', (json.dumps(urls), model_name))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'{content_type} added to {model_name}'})

@app.route('/api/transactions/<int:user_id>', methods=['GET'])
def get_transactions(user_id):
    conn = sqlite3.connect('stillapp.db')
    c = conn.cursor()
    c.execute('SELECT amount, type, model_name, content_type, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20', (user_id,))
    transactions = c.fetchall()
    conn.close()
    
    result = []
    for amount, tx_type, model_name, content_type, timestamp in transactions:
        result.append({
            'amount': amount,
            'type': tx_type,
            'model': model_name,
            'content_type': content_type,
            'timestamp': timestamp
        })
    
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
