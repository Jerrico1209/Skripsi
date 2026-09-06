import json
import requests
import time
import firebase_admin
import os
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

FIREBASE_URL = os.getenv("FIREBASE_URL")
bmkg_url = os.getenv("BMKG_URL")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID_TELEGRAM")
FIREBASE_CRED_JSON = os.getenv("FIREBASE_CRED_JSON")

if not firebase_admin._apps:
    if FIREBASE_CRED_JSON:
        # Dekode string JSON dari Environment Variable
        cred_dict = json.loads(FIREBASE_CRED_JSON)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback ke path lokal jika running di komputer sendiri
        CRED_PATH = os.getenv("FIREBASE_CRED_PATH", "credentials.json")
        cred = credentials.Certificate(CRED_PATH)

    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})

def kirim_notif(pesan):
    if not BOT_TOKEN or not CHAT_ID:
        print("Bot Token atau Chat ID belum diset di .env")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": pesan,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Gagal kirim notif Telegram: {e}")

last_status_atap = None

def callback_status_atap(event):
    global last_status_atap
    status_sekarang = event.data
    
    if status_sekarang != last_status_atap and status_sekarang is not None:
        status_clean = str(status_sekarang).lower().strip()
        
        if status_clean == "tertutup":
            pesan = "<b>PERINGATAN HUJAN!</b>\nSensor membaca adanya hujan. Atap otomatis <b>TERTUTUP</b>"
            kirim_notif(pesan)
            print("[INSTAN] Notifikasi Tertutup dikirim ke Telegram!")
        elif status_clean == "terbuka":
            pesan = "<b>INFO CUACA</b>\nKondisi sekarang sudah kering. Atap otomatis <b>TERBUKA!</b>"
            kirim_notif(pesan)
            print("[INSTAN] Notifikasi Terbuka dikirim ke Telegram!")

        last_status_atap = status_sekarang

ref_status = db.reference('status_atap')
ref_status.listen(callback_status_atap)
print("Listener Firebase Aktif! Memantau status_atap secara real-time...")

def pantau_dan_proses():
    global last_status_atap
    
    # 1. CEK API BMKG (Isolasi Error)
    is_hujan = False
    try:
        response = requests.get(bmkg_url)
        
        if response.status_code == 200:
            data = response.json()
            json_str = str(data)
            is_hujan = "Hujan" in json_str or "hujan" in json_str
            
            ref = db.reference('/perintah')
            ref.update({
                'bmkg_hujan': is_hujan,
                'last_update': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            print(f"BMKG Error HTTP Status: {response.status_code}")
    except Exception as e:
        print(f"Error saat mengambil data BMKG: {e}")

    # 2. BACA SENSOR HUJAN FISIK & LOG
    try:
        ref_sensor_hujan = db.reference('/sensor/hujan_1')
        sensor_hujan = ref_sensor_hujan.get()
        print(f"[{time.strftime('%H:%M:%S')}] BMKG Hujan: {is_hujan} | Sensor Hujan Fisik: {sensor_hujan}")
    except Exception as e:
        print(f"Error membaca sensor hujan: {e}")

while True:
    pantau_dan_proses()
    time.sleep(10)