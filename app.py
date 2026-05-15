from flask import Flask, render_template, request, jsonify
import subprocess
import os
from datetime import datetime
import json
import threading

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Tarix va fayllar uchun papkalar
os.makedirs('uploads', exist_ok=True)
os.makedirs('outputs', exist_ok=True)
os.makedirs('history', exist_ok=True)

HISTORY_FILE = 'history/history.json'

def load_history():
    """Tarixni o'qish"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(history):
    """Tarixni saqlash"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """Asosiy sahifa"""
    return render_template('index.html')

@app.route('/api/python', methods=['POST'])
def run_python():
    """Python kodini bajarish"""
    try:
        data = request.json
        code = data.get('code', '')
        
        if not code.strip():
            return jsonify({'error': 'Kod bo\'sh!'}), 400
        
        # Xavfsizlik uchun tekshirish
        dangerous_imports = ['os.system', '__import__', 'exec', 'eval']
        for danger in dangerous_imports:
            if danger in code and code.count('os.') > 3:
                return jsonify({'error': '⚠️ Xavfsizlik sabablari bilan bu buyruq qo\'llanilib bo\'lmaydi'}), 403
        
        # Kodni bajarish
        result = subprocess.run(
            ['python3', '-c', code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout if result.stdout else result.stderr
        
        # Tarixga qo'shish
        history = load_history()
        history.append({
            'type': 'python',
            'code': code[:200],
            'output': output[:500],
            'timestamp': datetime.now().isoformat(),
            'status': 'success' if result.returncode == 0 else 'error'
        })
        save_history(history[-50:])  # Oxirgi 50 ta
        
        return jsonify({
            'output': output,
            'status': 'success' if result.returncode == 0 else 'error'
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': '⏱️ Vaqt tugadi (30 soniya)'}), 408
    except Exception as e:
        return jsonify({'error': f'❌ Xato: {str(e)}'}), 500

@app.route('/api/bash', methods=['POST'])
def run_bash():
    """Bash buyruqlarini bajarish"""
    try:
        data = request.json
        command = data.get('command', '')
        
        if not command.strip():
            return jsonify({'error': 'Buyruq bo\'sh!'}), 400
        
        # Xavfsizlik tekshirish
        dangerous = ['rm -rf', 'mkfs', 'dd if=', ':(){:|:&', 'fork()']
        if any(d in command for d in dangerous):
            return jsonify({'error': '⚠️ Bu buyruq xavfsiz emas!'}), 403
        
        # Buyruqni bajarish
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout if result.stdout else result.stderr
        
        # Tarixga qo'shish
        history = load_history()
        history.append({
            'type': 'bash',
            'command': command[:200],
            'output': output[:500],
            'timestamp': datetime.now().isoformat(),
            'status': 'success' if result.returncode == 0 else 'error'
        })
        save_history(history[-50:])
        
        return jsonify({
            'output': output,
            'status': 'success' if result.returncode == 0 else 'error'
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': '⏱️ Vaqt tugadi (30 soniya)'}), 408
    except Exception as e:
        return jsonify({'error': f'❌ Xato: {str(e)}'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Fayl yuklash"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Fayl tanlanmagan'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Fayl nomemass'}), 400
        
        # Xavfsizlik
        allowed_extensions = {'txt', 'py', 'sh', 'json', 'csv', 'log', 'pdf', 'jpg', 'png'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'error': '❌ Bu format yo\'q!'}), 403
        
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join('uploads', filename)
        file.save(filepath)
        
        # Tarixga qo'shish
        history = load_history()
        history.append({
            'type': 'upload',
            'filename': filename,
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
        save_history(history[-50:])
        
        return jsonify({
            'message': '✅ Fayl yuklandi!',
            'filename': filename,
            'size': os.path.getsize(filepath)
        })
    
    except Exception as e:
        return jsonify({'error': f'❌ Xato: {str(e)}'}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """Yuklangan fayllarni ko'rsatish"""
    try:
        files = []
        for filename in os.listdir('uploads'):
            filepath = os.path.join('uploads', filename)
            files.append({
                'name': filename,
                'size': os.path.getsize(filepath),
                'created': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
            })
        
        return jsonify({'files': sorted(files, key=lambda x: x['created'], reverse=True)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Tarixni ko'rsatish"""
    try:
        history = load_history()
        return jsonify({'history': history[-20:]})  # Oxirgi 20 ta
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    """Tarixni tozalash"""
    try:
        save_history([])
        return jsonify({'message': '✅ Tarix tozalandi!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Server sog'lom ekanligini tekshirish"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'platform': 'Teacher AI Web Platform'
    })

if __name__ == '__main__':
    print("🚀 Server ishga tushmoqda: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
