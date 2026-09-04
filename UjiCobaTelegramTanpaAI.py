import telebot
import firebase_admin
from firebase_admin import credentials, db
import requests
from datetime import datetime

# --- SETUP API ---
TELEGRAM_BOT_TOKEN = "8601889522:AAEPuxz89mI9mOi_Jhp5eqDYgnMSx4MlJJU"
FIREBASE_URL = "https://ujicobaperintah-default-rtdb.asia-southeast1.firebasedatabase.app/"

#ALL
try:
# --- INISIALISASI FIREBASE ---
    try:
        # GANTI "nama_file_json_kamu.json" sesuai nama file kunci kamu
        cred = credentials.Certificate("ujicobaperintah-firebase-adminsdk-fbsvc-1599c0d837.json")
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print("Berhasil Connect ke Firebase!")
    except Exception as e:
        print(f"Gagal Firebase: {e}")

    # --- INISIALISASI TELEGRAM ---
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "Halo! Gunakan perintah /tutup untuk menutup jemuran, /buka untuk membuka jemuran, perintah /Prediksi untuk melihat prediksi cuaca dari BMKG, dan perintah /cek_ldr untuk cek intensitas cahaya.")

    #Command Tutup Atap
    @bot.message_handler(commands=['tutup'])
    def handle_tutup(message):
        try:
            # 1. Update data di Firebase
            ref = db.reference('status_atap')
            ref.set('tertutup')
            
            # 2. Balas dengan teks manual (tanpa AI)
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
            ref = db.reference('status_atap')
            ref.set('terbuka')
            
            pesan = "Perintah diterima! Atap jemuran sedang dibuka/\n\n[SISTEM]: Data di Firebase telah diubah menjadi 'terbuka'."
            bot.reply_to(message, pesan)
            
            print("Perintah /buka berhasil dikirim ke Firebase")
            
        except Exception as e:
            print(f"Error: {e}")    
    
    #Command Minta data dari BMKG
    @bot.message_handler(commands=['Prediksi'])
    def handle_bmkg(message):
        try:
            # 1. Beritahu user
            bot.reply_to(message, "Menghubungi API Publik BMKG... 🇮🇩")

            # 2. URL API BMKG Spesifik yang kamu berikan
            url = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=71.72.07.1005"
            
            response = requests.get(url)
            data = response.json()

            # 3. Ambil data prakiraan cuaca (biasanya indeks 0 adalah waktu terdekat)
            # Struktur JSON BMKG terbaru: data -> cuaca -> [indeks waktu]
            lokasi = data['data'][0]['lokasi']['desa']
            semua_prediksi = data['data'][0]['cuaca'] # Mengambil elemen pertama dari list cuaca
            
            waktu_sekarang = datetime.now()
            
            data_terdekat = None
            selisih_terkecil = float('inf')
            
            # Loop untuk mencari waktu yang paling dekat dengan jam sekarang
            #Loop untuk mencari waktu yang paling dekat dengan jam sekarang
            for blok_waktu in semua_prediksi:
                for prediksi in blok_waktu:
                    try:
                        # Menangani format '2026-04-23T12:00:00Z'
                        # Kita bersihkan 'T' jadi spasi dan 'Z' kita hapus
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
                    f"Gunakan /status_live untuk cek LDR sekarang."
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
        print("🚀 Sistem Manual Berjalan... Silakan tes di Telegram.")
    bot.polling()
    
except Exception as e:
    print(f"Error: {e}")