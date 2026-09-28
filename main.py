import os
import smtplib
from email.message import EmailMessage
import urllib.parse
import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import google.generativeai as genai

AI_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def search_realtime_posts(posisi, lokasi):
    """Pencarian real-time otomatis berdasarkan isian spreadsheet"""
    query = f"site:linkedin.com/posts/ {posisi} {lokasi} hiring email"
    print(f"🌐 Mencari dengan kueri: {query}")
    
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    posts_text = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('a', class_='result__snippet')
            for r in results:
                posts_text.append(r.get_text())
    except Exception as e:
        print(f"⚠️ Gagal mengambil data internet: {e}")
        
    return posts_text

def send_to_log(webhook_url, perusahaan, email, skor, status):
    """Mengirim data log otomatis ke Google Sheets"""
    if not webhook_url:
        return
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "tanggal": now,
        "perusahaan": perusahaan,
        "email": email,
        "skor": skor,
        "status": status
    }
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except:
        pass

def main():
    print("🤖 Bot LinkedIn CV Blaster Memulai Tugas...")
    
    config_url = os.environ.get("CONFIG_SHEET_URL")
    profile_url = os.environ.get("PROFILE_SHEET_URL")
    webhook_url = os.environ.get("LOG_WEBHOOK_URL")
    
    # Membaca data dari Google Sheets secara dinamis
    df_config = pd.read_csv(config_url)
    df_profile = pd.read_csv(profile_url)
    
    # Membersihkan spasi pada header tabel spreadsheet
    df_config.columns = df_config.columns.str.strip()
    config = dict(zip(df_config.iloc[:, 0].astype(str).str.strip(), df_config.iloc[:, 1].astype(str).str.strip()))
    profile = dict(zip(df_profile.iloc[:, 0].astype(str).str.strip(), df_profile.iloc[:, 1].astype(str).str.strip()))
    
    # Mengambil parameter murni dari Spreadsheet (Tanpa hardcode Python)
    posisi = config.get("posisi", "Digital Marketing Junior")
    lokasi = config.get("lokasi", "Jakarta")
    eligible_mode = str(config.get("eligible_mode", "ON")).upper()
    max_send = int(float(config.get("max_send_per_run", 5)))
    action_mode = str(config.get("action_mode", "send")).lower()
    
    print(f"📊 Konfigurasi Aktif -> Posisi: [{posisi}] | Lokasi: [{lokasi}] | Mode: [{action_mode}]")
    
    real_posts = search_realtime_posts(posisi, lokasi)
    if not real_posts:
        print("❌ Tidak ditemukan postingan lowongan baru saat ini.")
        return
        
    print(f"✨ Berhasil menarik {len(real_posts)} cuplikan postingan dari internet.")
    sent_count = 0
    
    for post in real_posts:
        if sent_count >= max_send:
            break
            
        print("\n-----------------------------------------")
        prompt = f"""
        Analisis teks postingan LinkedIn berikut:
        "{post}"
        
        Profil Pelamar:
        - Nama: {profile.get('nama_lengkap')}
        - Skill: {profile.get('ringkasan_skill')}
        - Link Portfolio & GDrive: {profile.get('gdrive_folder_cv')}
        - LinkedIn: {profile.get('linkedin_url')}
        
        Aturan Mode Eligible: {eligible_mode}
        
        Tugas Anda:
        1. Ekstrak Nama Perusahaan (jika ada, jika tidak tulis 'Perusahaan LinkedIn').
        2. Ekstrak Email tujuan HR. Jika tidak ada email, tulis EMAIL: TIDAK_ADA.
        3. Jika Mode Eligible 'ON', berikan penilaian skor kecocokan (0 sampai 100).
        4. Buat body email lamaran profesional yang menyertakan link folder GDrive pelamar.
        
        Format jawaban:
        PERUSAHAAN: [nama_perusahaan]
        EMAIL: [email_hr]
        SUBJECT: [subjek_email]
        SKOR: [angka_skor]
        BODY: [isi_surat_lamaran]
        """
        
        response = model.generate_content(prompt)
        ai_output = response.text
        
        try:
            lines = ai_output.split('\n')
            nama_pt = "Perusahaan LinkedIn"
            email_hr = ""
            subject_email = "Lamaran Pekerjaan"
            score = 100
            body_email = ""
            
            for line in lines:
                if line.startswith("PERUSAHAAN:"):
                    nama_pt = line.replace("PERUSAHAAN:", "").strip()
                elif line.startswith("EMAIL:"):
                    email_hr = line.replace("EMAIL:", "").strip()
                elif line.startswith("SUBJECT:"):
                    subject_email = line.replace("SUBJECT:", "").strip()
                elif line.startswith("SKOR:"):
                    try:
                        score = int(''.join(filter(str.isdigit, line)))
                    except:
                        score = 85
                elif line.startswith("BODY:"):
                    body_email = line.replace("BODY:", "").strip()
                    
            if not email_hr or "@" not in email_hr or email_hr == "TIDAK_ADA":
                print("⚠️ Dilewati karena tidak ada email HR yang valid.")
                continue
                
            if eligible_mode == "ON" and score < 70:
                print(f"⚠️ Melewatkan lowongan karena Skor AI ({score}) di bawah batas 70.")
                continue
                
            sender_email = os.environ.get("GMAIL_USER")
            sender_password = os.environ.get("GMAIL_APP_PASSWORD")
            
            msg = EmailMessage()
            msg['Subject'] = subject_email
            msg['From'] = sender_email
            msg['To'] = email_hr
            msg.set_content(body_email)
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender_email, sender_password)
                if action_mode == "send":
                    smtp.send_message(msg)
                    status_str = "Terkirim (Sent)"
                else:
                    smtp.sendmail(sender_email, [sender_email], msg.as_string())
                    status_str = "Draft/Arsip"
                    
            print(f"✅ Berhasil memproses lowongan ke {email_hr} [{status_str}]")
            send_to_log(webhook_url, nama_pt, email_hr, score, status_str)
            sent_count += 1
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
