import telebot
import firebase_admin
import os
import logging
import httpx
import requests
from datetime import datetime
from dotenv import load_dotenv
from firebase_admin import credentials, db
from openai import OpenAI

#Memanggil isi .env
load_dotenv()

#SETUP API
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIREBASE_URL = os.getenv("FIREBASE_URL")
CRED_PATH = os.getenv("FIREBASE_CRED_PATH")
API_KEY = os.getenv("AI_API_KEY")
AI_URL = os.getenv("AI_BASE_URL")
BMKG_URL = os.getenv("BMKG_URL")

#ALL
try:
#INISIALISASI FIREBASE
    try:
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print("Berhasil Connect ke Firebase!")
    except Exception as e:
        print(f"Gagal Firebase: {e}")

    # INISIALISASI HTTP CLIENT DAN OPENAI (DEEPSEEK)
    # trust_env=False mencegah Connection Error akibat proxy sistem
    http_client = httpx.Client(
        trust_env=False,
        timeout=30.0
    )

    client = OpenAI(
        api_key=API_KEY,
        base_url=AI_URL,
        http_client=http_client
    )

    # INISIALISASI TELEGRAM 
    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "Halo! \nGunakan perintah /tutup untuk menutup jemuran, \n/buka untuk membuka jemuran, \nperintah /Prediksi untuk melihat prediksi cuaca dari BMKG, \nperintah /cek_ldr untuk cek intensitas cahaya, \n/tanya_ai untuk menanyakan apakah jemuran harus ditutup atau tidak.")

    #Command Tutup Atap
    @bot.message_handler(commands=['tutup'])
    def handle_tutup(message):
        try:
            #Update data di Firebase
            ref = db.reference('status_atap')
            ref.set('tertutup')
            
            #Balas dengan teks
            pesan = "Perintah diterima! Atap jemuran sedang ditutup.\n\n[SISTEM]: Data di Firebase telah diubah menjadi 'tertutup'."
            bot.reply_to(message, pesan)
            
            print("Log: Perintah /tutup berhasil dikirim ke Firebase.")
            
        except Exception as e:
            print(f"Error: {e}")
            bot.reply_to(message, "Gagal mengupdate Firebase. Cek koneksi atau file kunci.")

    #Command Buka Atap
    @bot.message_handler(commands=['buka'])
    def handle_buka(message):
        try:
            # 1. Cek dulu kondisi sensor hujan & BMKG saat ini
            ref_sensor_hujan = db.reference('sensor/hujan_1')
            is_hujan_fisik = ref_sensor_hujan.get()
            
            ref_bmkg = db.reference('perintah/bmkg_hujan')
            is_bmkg_hujan = ref_bmkg.get()

            # 2. Jika sedang hujan fisik ATAU prediksi BMKG hujan, TOLAK perintah buka
            if is_hujan_fisik or is_bmkg_hujan:
                pesan_penolakan = (
                    "<b>PERINTAH DITOLAK!</b>\n\n"
                    "Sistem mendeteksi adanya hujan / prediksi hujan. "
                    "Atap tidak dapat dibuka demi keamanan jemuran!"
                )
                bot.reply_to(message, pesan_penolakan, parse_mode='HTML')
                print("Log: Perintah /buka ditolak karena terdeteksi hujan.")
                return

            # 3. Jika KERING, baru izinkan buka atap
            ref = db.reference('status_atap')
            ref.set('terbuka')
            
            pesan = "Perintah diterima! Atap jemuran sedang dibuka.\n\n[SISTEM]: Data di Firebase telah diubah menjadi 'terbuka'."
            bot.reply_to(message, pesan)
            
            print("Perintah /buka berhasil dikirim ke Firebase")
            
        except Exception as e:
            print(f"Error: {e}")
            bot.reply_to(message, "Gagal mengproses perintah buka.")  
    
    #Command Minta data dari BMKG
    @bot.message_handler(commands=['Prediksi'])
    def handle_bmkg(message):
        try:
            # 1. Beritahu user
            bot.reply_to(message, "Menghubungi API Publik BMKG... 🇮🇩")

            # 2. URL API BMKG Spesifik yang kamu berikan
            url = BMKG_URL
            
            response = requests.get(url)
            data = response.json()

            # 3. Ambil data prakiraan cuaca (biasanya indeks 0 adalah waktu terdekat)
            # Struktur JSON BMKG terbaru: data -> cuaca -> [indeks waktu]
            lokasi = data['data'][0]['lokasi']['desa']
            semua_prediksi = data['data'][0]['cuaca'] # Mengambil elemen pertama dari list cuaca
            
            waktu_sekarang = datetime.now()
            
            data_terdekat = None
            selisih_terkecil = float('inf')
            
            #Loop untuk mencari waktu yang paling dekat dengan jam sekarang
            for blok_waktu in semua_prediksi:
                for prediksi in blok_waktu:
                    try:
                        # Menangani format '2026-04-23T12:00:00Z'
                        # Hapus 'T' jadi spasi dan 'Z'
                        raw_waktu = prediksi['datetime'].replace('T', ' ').replace('Z', '')
                        waktu_api = datetime.strptime(raw_waktu, '%Y-%m-%d %H:%M:%S')
                        
                        # Hitung selisih detik
                        selisih = abs((waktu_sekarang - waktu_api).total_seconds())
                        
                        if selisih < selisih_terkecil:
                            selisih_terkecil = selisih
                            data_terdekat = prediksi
                    except Exception as e:
                        print(f"Gagal memproses waktu {prediksi['datetime']}: {e}")
                        continue

            if data_terdekat:
                kondisi = data_terdekat['weather_desc']
                suhu = data_terdekat['t']
                kelembapan = data_terdekat['hu']
                waktu_data = data_terdekat['datetime']

                if "Hujan" in kondisi:
                    saran = "<b>PERINGATAN:</b> Berdasarkan jam terdekat, BMKG memprediksi HUJAN."
                else:
                    saran = "<b>INFO:</b> Kondisi jam ini menurut BMKG terpantau AMAN."

                pesan = (
                    f"<b>DATA BMKG REAL-TIME</b>\n"
                    f"Lokasi: {lokasi}\n"
                    f"----------------------------------\n"
                    f"Waktu Data: {waktu_data}\n"
                    f"Kondisi: <b>{kondisi}</b>\n"
                    f"Suhu: {suhu}°C\n"
                    f"Kelembapan: {kelembapan}%\n\n"
                    f"{saran}\n"
                    f"----------------------------------\n"
                    f"Gunakan /cek_ldr untuk cek LDR sekarang."
                )
                bot.send_message(message.chat.id, pesan, parse_mode='HTML')
            else:
                bot.reply_to(message, "Tidak ditemukan data cuaca yang cocok.")

        except Exception as e:
            print(f"Error Detail: {e}")
            bot.reply_to(message, f"Gagal sinkronisasi waktu API: {e}")

    @bot.message_handler(commands=['cek_ldr'])
    def send_ldr(message):
        # Mengambil nilai dari path 'sensor/ldr' di Firebase
        ref = db.reference('sensor/ldr')
        nilai_ldr = ref.get()
        
        response = f"Nilai LDR saat ini: {nilai_ldr}"
        bot.reply_to(message, response)
        print("Sistem Manual Berjalan... Silakan tes di Telegram.")
    
    @bot.message_handler(commands=['tanya_ai'])
    def AI(message):
        print("Log: Command /tanya_ai masuk ke server")
        bot.reply_to(message, "Menunggu jawaban AI...")
        
        try:
            ref = db.reference('sensor/ldr')
            nilai_ldr = ref.get()
            
            ref_hujan = db.reference('sensor/hujan_1')
            status_hujan = ref_hujan.get()
            
            ref_bmkg = db.reference('perintah/bmkg_hujan')
            bmkg_hujan = ref_bmkg.get()
            
            kondisi_hujan = "Terdeteksi Basah/Hujan" if status_hujan else "Kering/Tidak Hujan"
            prediksi_bmkg = "Hujan" if bmkg_hujan else "Cerah/Aman"
            
            prompt_user = (
                f"Data Sensor Saat Ini:\n"
                f"- Nilai LDR: {nilai_ldr} (Skala ADC 0-1023, di mana nilai > 700 berarti MENDUNG/GELAP, dan < 300 berarti TERANG/CERAH)\n"
                f"- Sensor Air Fisik: {kondisi_hujan}\n"
                f"- Prediksi BMKG: {prediksi_bmkg}\n\n"
                f"Apakah saat ini akan/sedang hujan? Dan apakah saya sebaiknya menutup atau membuka jemuran? "
                f"Berikan jawaban singkat dan langsung ke intinya."
            )
    
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "Kamu adalah asisten pintar untuk sistem jemuran otomatis. "
                            "Pahami bahwa pada LDR pengguna, semakin TINGGI nilainya mendekati 1023 berarti kondisi semakin MENDUNG/GELAP, "
                            "dan semakin RENDAH nilainya mendekati 0 berarti kondisi semakin TERANG/CERAH. "
                            "Gunakan Bahasa Indonesia yang ramah, singkat, dan berikan rekomendasi aksi yang jelas (TUTUP atau BUKA jemuran)."
                        )
                    },
                    {"role": "user", "content": prompt_user}
                ],
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}}
            )
            
            jawaban_ai = response.choices[0].message.content
            bot.reply_to(message, jawaban_ai)
            
        except Exception as e:
            print(f"Error: {e}")
            bot.reply_to(message, f"Gagal mendapatkan respon AI: {e}")
            
    print("Bot siap berjalan!")
    bot.polling(non_stop=True, skip_pending=True)
    
except Exception as e:
    print(f"Error: {e}")