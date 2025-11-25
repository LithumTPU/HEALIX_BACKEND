from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import traceback

app = Flask(__name__)
CORS(app)

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

@app.route('/api/config/read', methods=['GET'])
def config_read():
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r') as f:
                data = json.load(f)
            print(f"[CONFIG] Read config from {CONFIG_FILE_PATH}")
            return jsonify({'config': data})
        else:
            print(f"[CONFIG] Config file not found at {CONFIG_FILE_PATH}")
            return jsonify({'config': None})
    except Exception as e:
        print(f"[CONFIG ERROR] Failed to read config: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/write', methods=['POST'])
def config_write():
    try:
        data = request.get_json(force=True)
        config = data.get('config')
        if not config:
            return jsonify({'error': 'no config provided'}), 400
        
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"[CONFIG] Wrote config to {CONFIG_FILE_PATH}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[CONFIG ERROR] Failed to write config: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/clear', methods=['POST'])
def config_clear():
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            os.remove(CONFIG_FILE_PATH)
            print(f"[CONFIG] Cleared config file at {CONFIG_FILE_PATH}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[CONFIG ERROR] Failed to clear config: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Config server running'})

if __name__ == '__main__':
    print("Starting Config Server...")
    print(f"Config file path: {CONFIG_FILE_PATH}")
    app.run(host='0.0.0.0', port=5002, debug=False)
