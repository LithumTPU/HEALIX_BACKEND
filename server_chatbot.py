from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback
from chatbot_web import run_chatbot
import sys  # Add this import at the top

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def api_chat():
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json(force=True)
    message = data.get('message')
    print(f"[DEBUG] Received message: {message}")

    if not message:
        return jsonify({'error': 'no message provided'}), 400

    try:
        reply = run_chatbot(message)
        print(f"[DEBUG] Sending reply: {reply[:100]}...")
        return jsonify({'reply': reply})

    except Exception as e:
        print(f"[ERROR] API error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Chatbot server is running'})

if __name__ == '__main__':
    print("Starting Chatbot Server...")
    print(f"Python executable: {sys.executable}")
    app.run(host='0.0.0.0', port=5000, debug=False)