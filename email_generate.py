from typing import Dict, List, Any
import json
import requests
from datetime import datetime
import yagmail

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
    except Exception as e:
        print(f"Error fetching Firebase data: {e}")
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
    """Determine status of a vital sign."""
    status = {"level": "NORMAL", "description": "", "action": "Continue monitoring"}

    def _num(v):
        try: return float(v)
        except: return None

    cfg = _num(thresholds.get(vital))

    # Specialized logic for known vitals
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

    else: # fallback
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
    except: return "Unknown"

# -------------------- Next Review --------------------
def get_next_review_time(critical: int, warnings: int) -> str:
    if critical>0: return "Immediate continuous monitoring"
    elif warnings>0: return "Within 1-2 hours"
    else: return "Routine 4-6 hours"

# -------------------- Generate Patient Messages --------------------
def generate_comprehensive_messages(patient_id: str, pdata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate email summary only"""
    thresholds = config.get("thresholds", {}) or {}
    notifications = config.get("notificationTypes", []) or []
    email_summary = []

    timestamps = pdata.get("timestamp",[]) or []
    n=len(timestamps)
    if n==0: return {"email":[]}

    vitals = [k for k in pdata.keys() if k not in RESERVED_FIELDS]
    
    # Detailed Readings & Email Filtering
    critical_count=0
    warning_count=0
    for i, ts in enumerate(timestamps):
        for v in vitals:
            vals = pdata.get(v,[])
            if isinstance(vals, dict): vals=[vals[k] for k in sorted(vals.keys(), key=lambda x:int(x) if str(x).isdigit() else x)]
            if not vals or i>=len(vals): continue
            val=vals[i]
            status=get_vital_status(v,val,thresholds)
            
            if status['level'] in ['CRITICAL','SEVERE']:
                msg=f"[{ts}] {v.title()}: {val} | {status['level']} | {status['description']} | Action: {status['action']}"
                email_summary.append(msg)
                critical_count+=1
            elif status['level'] in ['HIGH','LOW','ELEVATED','MODERATE'] and "health_alerts" in notifications:
                msg=f"[{ts}] {v.title()}: {val} | {status['level']} | {status['description']} | Action: {status['action']}"
                email_summary.append(msg)
                warning_count+=1

        # Medication reminder
        if pdata.get("food_provided") and "medication_reminders" in notifications:
            food_times=[ft for ft in pdata.get("food_provided") if ft<=ts]
            if food_times:
                last_food=max(food_times)
                td=calculate_time_difference(last_food,ts)
                email_summary.append(f"[{ts}] Last medication/meal: {last_food} ({td} ago)")
    
    next_review = get_next_review_time(critical_count,warning_count)
    email_summary.append(f"Next review: {next_review}")

    return {"email":email_summary}

# -------------------- Send Email --------------------
def send_email(config: Dict[str,Any], patient_id:str, body:str):
    user=config.get("senderEmail")
    password=config.get("emailAppPassword")
    to_email=config.get("primaryEmail")
    backup=config.get("backupEmail")
    subject_prefix=config.get("subjectPrefix","[HealthBot]")
    subject=f"{subject_prefix} Patient {patient_id} Status Alert"
    
    try:
        yag=yagmail.SMTP(user=user,password=password)
        yag.send(to=[to_email,backup] if backup else [to_email], subject=subject, contents=body)
        print(f"Email sent for {patient_id}")
    except Exception as e:
        print(f"Failed to send email for {patient_id}: {e}")

# -------------------- Test Email --------------------
def send_test_email(config: Dict[str, Any]):
    try:
        user = config.get("senderEmail")
        password = config.get("emailAppPassword")
        to_email = config.get("primaryEmail")
        backup = config.get("backupEmail")
        subject_prefix = config.get("subjectPrefix", "[HealthBot]")

        subject = f"{subject_prefix} - Test Alert"
        body = (
            "This is a Healix test notification.\n\n"
            "If you received this email, email alerting is configured correctly."
        )

        yag = yagmail.SMTP(user=user, password=password)
        recipients = [to_email]
        if backup:
            recipients.append(backup)
        yag.send(to=recipients, subject=subject, contents=body)
        print(f"Test email sent to: {recipients}")
        return True
    except Exception as e:
        print(f"Failed to send test email: {e}")
        return False

# -------------------- Main Callable Function --------------------
def email_healix():
    try:
        config = load_config("config.json")
        raw_data = fetch_firebase_data()
        firebase_data = format_firebase_data(raw_data)

        for pid, pdata in firebase_data.get("patients", {}).items():
            result = generate_comprehensive_messages(pid, pdata, config)
            if result["email"]:
                send_email(config, pid, "\n".join(result["email"]))
        
        print(f"[{datetime.now().isoformat()}] Email alerts processed successfully")
    except Exception as e:
        print(f"[ERROR] email_healix() failed: {e}")

# -------------------- Entry Point --------------------
if __name__ == "__main__":
    email_healix()