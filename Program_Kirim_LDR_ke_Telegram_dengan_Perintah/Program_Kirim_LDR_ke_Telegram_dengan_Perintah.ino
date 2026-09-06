#include <ESP8266WiFi.h>
#include <FirebaseESP8266.h>
#include <Servo.h>

#define WIFI_SSID "E'en"
#define WIFI_PASSWORD "WalangitanKahiking12082001"

#define FIREBASE_HOST "ujicobaperintah-default-rtdb.asia-southeast1.firebasedatabase.app"
#define FIREBASE_AUTH "PVkAEe8PV1ItxYNIbYfSu9r2xMSqjeA6p81QIcoF"

const int pinLDR = A0;
const int pinHujan1 = D2;
#define SERVO_PIN D4

FirebaseData firebaseData;
FirebaseConfig config;
FirebaseAuth auth;
Servo myServo;

unsigned long lastFirebaseSend = 0;
const unsigned long firebaseInterval = 2000; // Cek & Kirim data tiap 2 detik

String statusAtapFirebase = "terbuka"; // Penampung perintah Telegram
String statusAtapTerakhir = "";        // Mencegah spam kirim data ke Firebase

bool bmkgHujanFromPython = false;

void setup() {
  Serial.begin(115200);
  pinMode(pinHujan1, INPUT);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(300);
  }
  Serial.println("\nConnected!");

  config.host = FIREBASE_HOST;
  config.signer.tokens.legacy_token = FIREBASE_AUTH;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  myServo.attach(SERVO_PIN, 544, 2400);
  myServo.write(0);
}

void loop() {
  yield();

  int nilaiLDR = analogRead(pinLDR);
  bool isHujanFisik = (digitalRead(pinHujan1) == LOW);

  // Tugas Periodik: Baca Perintah Python & Kirim Sensor (Tiap 2 Detik)
  if (millis() - lastFirebaseSend >= firebaseInterval) {
    lastFirebaseSend = millis();

    // 1. Baca Perintah Hujan BMKG hasil olahan Python
    if (Firebase.getBool(firebaseData, "/perintah/bmkg_hujan")) {
      bmkgHujanFromPython = firebaseData.boolData();
    }

    // 2. baca Perintah status atap dari telegram
    if (Firebase.getString(firebaseData, "status_atap")) {
      statusAtapFirebase = firebaseData.stringData();

    // 3. Kirim Data Sensor Fisik ke Firebase
    Firebase.setInt(firebaseData, "/sensor/ldr", nilaiLDR);
    Firebase.setBool(firebaseData, "/sensor/hujan_1", isHujanFisik);

    Serial.print("LDR: "); Serial.print(nilaiLDR);
    Serial.print(" | Hujan Fisik: "); Serial.print(isHujanFisik);
    Serial.print(" | BMKG (Python): "); Serial.println(bmkgHujanFromPython);
    }
  }

  // LOGIKA KONTROL SERVO
  // SKENARIO 1: Keamanan Utama (Sensor Basah / BMKG Hujan) -> Paksa Tertutup
  if (isHujanFisik || bmkgHujanFromPython) {
    myServo.write(180); // Tutup Servo
    
    // Update Firebase HANYA jika status belum tertutup
    if (statusAtapTerakhir != "tertutup") {
      Firebase.setString(firebaseData, "status_atap", "tertutup");
      statusAtapTerakhir = "tertutup";
    }
  } 
  // SKENARIO 2: Kondisi Kering -> Patuhi Perintah Manual dari Telegram
  else {
    if (statusAtapFirebase == "tertutup") {
      myServo.write(180); // Tutup Servo karena perintah Telegram /tutup
      statusAtapTerakhir = "tertutup";
    } 
    else {
      myServo.write(0);   // Buka Servo karena perintah Telegram /buka atau kondisi normal
      
      // Update Firebase HANYA jika status sebelumnya belum terbuka
      if (statusAtapTerakhir != "terbuka") {
        Firebase.setString(firebaseData, "status_atap", "terbuka");
        statusAtapTerakhir = "terbuka";
      }
    }
  }
}