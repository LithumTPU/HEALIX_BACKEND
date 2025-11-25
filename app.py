import os
from flask import Flask, Blueprint, request, jsonify
from flask_cors import CORS

# Import existing modules (their top-level definitions remain intact)
import server_config
import server_chatbot
import chatbot_web
import tts_server
import log_server
import log_saver
import email_server


def create_app():
    app = Flask(__name__)
    CORS(app)

    # --- Config module routes (prefix /config) ---
    config_bp = Blueprint('config', __name__, url_prefix='/config')

    @config_bp.route('/read', methods=['GET'])
    def config_read():
        return server_config.config_read()

    @config_bp.route('/write', methods=['POST'])
    def config_write():
        return server_config.config_write()

    @config_bp.route('/clear', methods=['POST'])
    def config_clear():
        return server_config.config_clear()

    @config_bp.route('/health', methods=['GET'])
    def config_health():
        return server_config.health()

    app.register_blueprint(config_bp)

    # --- Chatbot module routes (prefix /chatbot) ---
    chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')

    # Use server_chatbot.api_chat which uses chatbot_web.run_chatbot internally
    @chatbot_bp.route('/api/chat', methods=['POST', 'OPTIONS'])
    def api_chat():
        return server_chatbot.api_chat()

    @chatbot_bp.route('/run', methods=['POST'])
    def run_chat():
        data = request.get_json(silent=True) or {}
        prompt = data.get('message') or data.get('prompt') or ''
        if not prompt:
            return jsonify({'error': 'no message provided'}), 400
        try:
            reply = chatbot_web.run_chatbot(prompt)
            return jsonify({'reply': reply})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbot_bp.route('/health', methods=['GET'])
    def chatbot_health():
        return server_chatbot.health_check()

    app.register_blueprint(chatbot_bp)

    # --- TTS module routes (prefix /tts) ---
    tts_bp = Blueprint('tts', __name__, url_prefix='/tts')

    @tts_bp.route('/api/tts', methods=['POST', 'OPTIONS'])
    def api_tts():
        return tts_server.api_tts()

    @tts_bp.route('/health', methods=['GET'])
    def tts_health():
        return tts_server.health()

    app.register_blueprint(tts_bp)

    # --- Logs module routes (prefix /logs) ---
    logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

    @logs_bp.route('/api/logs', methods=['GET'])
    def get_all_logs():
        return log_server.get_all_logs()

    @logs_bp.route('/api/regenerate_logs', methods=['GET'])
    def regenerate_logs():
        return log_server.regenerate_logs()

    app.register_blueprint(logs_bp)

    # --- Email module routes (prefix /email) ---
    email_bp = Blueprint('email', __name__, url_prefix='/email')

    @email_bp.route('/service/status', methods=['GET'])
    def email_status():
        return email_server.email_service_status()

    @email_bp.route('/service/enable', methods=['POST'])
    def email_enable():
        return email_server.email_service_enable()

    @email_bp.route('/service/disable', methods=['POST'])
    def email_disable():
        return email_server.email_service_disable()

    @email_bp.route('/service/send-now', methods=['POST'])
    def email_send_now():
        return email_server.email_service_send_now()

    @email_bp.route('/service/send-test', methods=['POST'])
    def email_send_test():
        return email_server.email_service_send_test()

    @email_bp.route('/health', methods=['GET'])
    def email_health():
        try:
            return email_server.health_check()
        except Exception:
            return jsonify({'status': 'unknown'}), 500

    app.register_blueprint(email_bp)

    # --- Root health check that aggregates module healths ---
    @app.route('/health', methods=['GET'])
    def health():
        statuses = {}
        try:
            statuses['config'] = server_config.health().get_json()
        except Exception:
            statuses['config'] = {'status': 'unavailable'}
        try:
            statuses['chatbot'] = server_chatbot.health_check().get_json()
        except Exception:
            statuses['chatbot'] = {'status': 'unavailable'}
        try:
            statuses['tts'] = tts_server.health().get_json()
        except Exception:
            statuses['tts'] = {'status': 'unavailable'}
        try:
            statuses['email'] = email_server.health_check().get_json()
        except Exception:
            statuses['email'] = {'status': 'unavailable'}

        return jsonify({'status': 'ok', 'components': statuses})

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting unified server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

