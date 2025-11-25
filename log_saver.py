# healthbot_core.py
from typing import Dict, List, Any
import json
import requests
from datetime import datetime
from pathlib import Path

# -------------------- Firebase Config --------------------
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyAefgeoFaztmjsTm56W2LZchavUC8hDY_o",
    "authDomain": "healthbot-e8438.firebaseapp.com",
    "databaseURL": "https://healthbot-e8438-default-rtdb.firebaseio.com",
    "projectId": "healthbot-e8438",
    "storageBucket": "healthbot-e8438.appspot.com",
    "messagingSenderId": "555833461576",
    "appId": "1:555833461576:web:45f802862d25a33b49017d",
    "measurementId": "G-EDG9PFW99H"
}

RESERVED_FIELDS = {"timestamp", "food_provided", "patient", "patientId"}
LOG_DIR = Path("logs")

# -------------------- Load Config --------------------
def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        return json.load(f)

# -------------------- Fetch Firebase Data --------------------
def fetch_firebase_data() -> Dict[str, Any]:
    url = FIREBASE_CONFIG["databaseURL"] + "/.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data if data else {"patients": {}}
    except Exception:
        return {"patients": {}}

# -------------------- Format Firebase Data --------------------
def format_firebase_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    formatted = {"patients": {}}
    if "patients" not in raw_data:
        return formatted
    for pid, pdata in raw_data["patients"].items():
        formatted["patients"][pid] = {}
        for key in ['temperature', 'heartRate', 'spo2', 'respiratoryRate',
                    'systolic', 'diastolic', 'pain_scale', 'food_provided', 'timestamp']:
            if key in pdata:
                value = pdata[key]
                if isinstance(value, dict):
                    formatted["patients"][pid][key] = [value[k] for k in sorted(value.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)]
                elif isinstance(value, list):
                    formatted["patients"][pid][key] = value
                else:
                    formatted["patients"][pid][key] = [value]
    return formatted

# -------------------- Discover Vitals --------------------
def discover_vitals(firebase_data: Dict[str, Any]) -> List[str]:
    keys = set()
    for pid, pdata in firebase_data.get("patients", {}).items():
        if not isinstance(pdata, dict):
            continue
        for k in pdata.keys():
            if k not in RESERVED_FIELDS:
                keys.add(k)
    return sorted(keys)

# -------------------- Vital Status --------------------
def get_vital_status(vital: str, value: float, thresholds: Dict[str, Any]) -> Dict[str, str]:
    status = {"level": "NORMAL", "description": "", "action": "Continue monitoring"}

    def _num(v):
        try: return float(v)
        except: return None

    cfg = _num(thresholds.get(vital))

    # specialized logic for known vitals
    if vital == "temperature":
        if value < 36.1:
            status.update({"level":"LOW","description":"Hypothermia risk","action":"Provide warming measures"})
        elif cfg and value > cfg:
            status.update({"level":"HIGH","description":"Fever detected","action":"Administer antipyretics"})
        elif value > 37.5:
            status.update({"level":"ELEVATED","description":"Mild fever","action":"Monitor frequently"})
        else:
            status["description"] = "Temperature normal"

    elif vital == "heartRate":
        if value < 60: status.update({"level":"LOW","description":"Bradycardia","action":"Check consciousness/meds"})
        elif cfg and value > cfg + 20: status.update({"level":"CRITICAL","description":"Severe tachycardia","action":"IMMEDIATE intervention"})
        elif cfg and value > cfg: status.update({"level":"HIGH","description":"Tachycardia","action":"Assess for pain/infection"})
        elif value > 100: status.update({"level":"HIGH","description":"Tachycardia","action":"Assess for pain/infection"})
        else: status["description"] = "Heart rate normal"

    elif vital == "spo2":
        if cfg and value < cfg - 5: status.update({"level":"CRITICAL","description":"Severe hypoxemia","action":"Provide oxygen immediately"})
        elif cfg and value < cfg: status.update({"level":"LOW","description":"Hypoxemia","action":"Start oxygen therapy"})
        elif value < 95: status.update({"level":"BORDERLINE","description":"Borderline oxygen","action":"Increase monitoring"})
        else: status["description"] = "Oxygen normal"

    elif vital == "respiratoryRate":
        if value < 12: status.update({"level":"LOW","description":"Bradypnea","action":"Check airway"})
        elif cfg and value > cfg: status.update({"level":"HIGH","description":"Tachypnea","action":"Assess respiratory distress"})
        elif value > 20: status.update({"level":"ELEVATED","description":"Mildly elevated RR","action":"Monitor"})
        else: status["description"] = "Respiratory rate normal"

    elif vital == "systolic":
        if value < 90: status.update({"level":"LOW","description":"Hypotension","action":"Assess shock"})
        elif cfg and value > cfg: status.update({"level":"HIGH","description":"Hypertension","action":"Review meds"})
        elif value > 130: status.update({"level":"ELEVATED","description":"Pre-hypertension","action":"Monitor"})
        else: status["description"] = "Systolic normal"

    elif vital == "diastolic":
        if value < 60: status.update({"level":"LOW","description":"Low diastolic","action":"Monitor"})
        elif cfg and value > cfg: status.update({"level":"HIGH","description":"Elevated diastolic","action":"Assess CV risk"})
        else: status["description"] = "Diastolic normal"

    elif vital == "pain_scale":
        if value >= 8: status.update({"level":"SEVERE","description":"Severe pain","action":"Administer analgesics"})
        elif cfg and value >= cfg: status.update({"level":"MODERATE","description":"Moderate pain","action":"Provide pain meds"})
        elif value >= 4: status.update({"level":"MILD","description":"Mild pain","action":"Monitor"})
        else: status["description"] = "Pain minimal"

    else:
        if cfg:
            if value > cfg*1.2: status.update({"level":"CRITICAL","description":"Above threshold","action":"Intervene"})
            elif value > cfg: status.update({"level":"HIGH","description":"Above threshold","action":"Monitor"})
            else: status["description"] = "Within threshold"
        else:
            status["description"] = f"{vital}: {value} (no threshold)"

    return status

# -------------------- Trend Calculation --------------------
def calculate_trends(values: List[float]) -> Dict[str, Any]:
    if len(values) < 2:
        return {"trend":"insufficient_data","change":0,"description":""}
    recent = sum(values[-3:])/min(3,len(values[-3:]))
    older = sum(values[:3])/min(3,len(values[:3]))
    change = recent - older
    pct = (change/older*100) if older !=0 else 0
    if abs(pct)<2: trend, desc = "stable","Minimal variation"
    elif change>0: trend, desc = "increasing", f"Up {pct:.1f}%"
    else: trend, desc = "decreasing", f"Down {abs(pct):.1f}%"
    return {"trend":trend,"change":change,"percent_change":pct,"description":desc,"min":min(values),"max":max(values),"avg":sum(values)/len(values)}

# -------------------- Time Difference --------------------
def calculate_time_difference(time1: str, time2: str) -> str:
    try:
        t1=datetime.strptime(time1,"%Y-%m-%d %H:%M:%S")
        t2=datetime.strptime(time2,"%Y-%m-%d %H:%M:%S")
        diff = abs((t2-t1).total_seconds())
        h=int(diff//3600)
        m=int((diff%3600)//60)
        return f"{h}h {m}m" if h>0 else f"{m}m"
    except:
        return "Unknown"

# -------------------- Next Review --------------------
def get_next_review_time(critical: int, warnings: int) -> str:
    if critical>0: return "Immediate continuous monitoring"
    elif warnings>0: return "Within 1-2 hours"
    else: return "Routine 4-6 hours"

# -------------------- Generate Patient Messages --------------------
def generate_comprehensive_messages(patient_id: str, pdata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    thresholds = config.get("thresholds", {}) or {}
    messages = []

    timestamps = pdata.get("timestamp",[]) or []
    if not timestamps:
        return {"messages":["No data available"]}

    vitals = [k for k in pdata.keys() if k not in RESERVED_FIELDS]

    # Trend Analysis
    for v in vitals:
        vals = pdata.get(v,[])
        if isinstance(vals, dict): vals = [vals[k] for k in sorted(vals.keys(), key=lambda x:int(x) if str(x).isdigit() else x)]
        if not vals: continue
        trend = calculate_trends(vals)
        messages.append(f"{v.title()} - Current:{vals[-1]} Avg:{trend['avg']:.1f} Min:{trend['min']} Max:{trend['max']} Trend:{trend['trend']}")

    return {"messages":messages}

LOG_DIR.mkdir(parents=True, exist_ok=True)

def save_patient_logs(patient_id: str, messages: List[str]):
    """
    Persist one JSON file per patient under ./logs.
    Overwrites the file each run; change to timestamped filenames if you prefer history.
    """
    log_file = LOG_DIR / f"{patient_id}.json"
    payload = {
        "patient_id": patient_id,
        "generated_at": datetime.now().isoformat(),
        "messages": messages
    }
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Saved logs for {patient_id} -> {log_file}")
    except Exception as e:
        print(f"Failed to save logs for {patient_id}: {e}")

# Add a simple runnable entry point that generates messages and saves logs
if __name__ == "__main__":
    try:
        config = load_config("config.json")
    except Exception as e:
        print(f"Could not load config.json, continuing with empty config: {e}")
        config = {}

    raw_data = fetch_firebase_data()
    firebase_data = format_firebase_data(raw_data)

    for pid, pdata in firebase_data.get("patients", {}).items():
        result = generate_comprehensive_messages(pid, pdata, config)
        # Save JSON logs for each patient
        save_patient_logs(pid, result.get("messages", []))
