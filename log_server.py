from flask import Flask, jsonify
from pathlib import Path
import json

# Import functions from log_saver
from log_saver import fetch_firebase_data, format_firebase_data, generate_comprehensive_messages, save_patient_logs, load_config, LOG_DIR

app = Flask(__name__)
LOG_DIR.mkdir(parents=True, exist_ok=True)

@app.route("/api/logs")
def get_all_logs():
    logs = {}
    for file in LOG_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                logs[file.stem] = json.load(f)
        except Exception as e:
            logs[file.stem] = {"error": str(e)}
    return jsonify(logs)

# New endpoint to regenerate logs on demand
@app.route("/api/regenerate_logs")
def regenerate_logs():
    try:
        config = load_config("config.json")
    except Exception:
        config = {}

    raw_data = fetch_firebase_data()
    firebase_data = format_firebase_data(raw_data)

    for pid, pdata in firebase_data.get("patients", {}).items():
        result = generate_comprehensive_messages(pid, pdata, config)
        save_patient_logs(pid, result.get("messages", []))

    return jsonify({"status": "success", "message": "Logs regenerated"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
