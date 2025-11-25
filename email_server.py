from flask import Flask, jsonify
from flask_cors import CORS
import threading
import time
from email_generate import email_healix, send_test_email

app = Flask(__name__)
CORS(app)

# Global state for email service
email_thread = None
stop_event = threading.Event()
service_lock = threading.Lock()

def run_email_continuously():
    """Background thread that runs email_healix continuously until stop_event is set."""
    print("[EMAIL_WORKER] Started continuous email loop")
    while not stop_event.is_set():
        try:
            email_healix()
            print("[EMAIL_WORKER] Email alerts sent successfully")
        except Exception as e:
            print(f"[EMAIL_WORKER] Error: {e}")
        
        # Small sleep to prevent CPU spike (optional; adjust or remove as needed)
        time.sleep(1)
    
    print("[EMAIL_WORKER] Email service stopped")

@app.route('/api/email-service/status', methods=['GET'])
def email_service_status():
    """Get current status of the email service."""
    is_running = email_thread is not None and email_thread.is_alive()
    return jsonify({
        'enabled': is_running,
        'message': 'Email alerts are ' + ('enabled' if is_running else 'disabled')
    })

@app.route('/api/email-service/enable', methods=['POST'])
def email_service_enable():
    """Enable the email alert service."""
    global email_thread, stop_event
    
    with service_lock:
        # Check if already running
        if email_thread is not None and email_thread.is_alive():
            return jsonify({'status': 'already_enabled', 'message': 'Email service is already running'}), 200
        
        # Clear stop event and start new thread
        stop_event.clear()
        email_thread = threading.Thread(target=run_email_continuously, daemon=True)
        email_thread.start()
        
        print("[EMAIL_SERVER] Email service enabled")
        return jsonify({'status': 'success', 'message': 'Email service enabled'}), 200

@app.route('/api/email-service/disable', methods=['POST'])
def email_service_disable():
    """Disable the email alert service."""
    global email_thread, stop_event
    
    with service_lock:
        # Signal thread to stop
        stop_event.set()
        
        # Wait for thread to finish (max 2 seconds)
        if email_thread is not None and email_thread.is_alive():
            email_thread.join(timeout=2)
        
        email_thread = None
        print("[EMAIL_SERVER] Email service disabled")
        return jsonify({'status': 'success', 'message': 'Email service disabled'}), 200

@app.route('/api/email-service/send-now', methods=['POST'])
def email_service_send_now():
    """Manually trigger email alert generation immediately."""
    try:
        email_healix()
        print("[EMAIL_SERVER] Manual email alert triggered")
        return jsonify({'status': 'success', 'message': 'Email alerts sent'}), 200
    except Exception as e:
        print(f"[EMAIL_SERVER] Error sending emails: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/email-service/send-test', methods=['POST'])
def email_service_send_test():
    """Send a one-off test email to configured recipient(s)."""
    try:
        config = None
        try:
            # Attempt to read config.json from project root
            import json, os
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
        except Exception as e:
            print("[EMAIL_SERVER] Could not load config.json:", e)
            config = None

        if not config:
            return jsonify({'status': 'error', 'message': 'Missing configuration'}), 500

        ok = send_test_email(config)
        if ok:
            print("[EMAIL_SERVER] Test email sent")
            return jsonify({'status': 'success', 'message': 'Test email sent'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send test email'}), 500
    except Exception as e:
        print("[EMAIL_SERVER] Error in send-test:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    is_running = email_thread is not None and email_thread.is_alive()
    return jsonify({
        'status': 'ok',
        'message': 'Email server running',
        'email_service_enabled': is_running
    })

if __name__ == '__main__':
    print("Starting Email Server...")
    app.run(host='0.0.0.0', port=5003, debug=False)
