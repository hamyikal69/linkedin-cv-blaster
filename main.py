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

# Solusi Error 404: Menggunakan model gemini-pro yang kompatibel dengan server
model = genai.GenerativeModel('gemini-pro')

def search_realtime_posts(posisi, lokasi, user_email):
    # Solusi Anti-Blokir: Tetap menggunakan Yahoo Search
    queries = [
        f'site:linkedin.com/posts/ "{posisi}" {lokasi} "@gmail.com" OR "@yahoo.com"',
        f'site:linkedin.com "{posisi}" hiring "send your cv"'
    ]
    
    posts_text = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    for query in queries:
        print(f"🌐 Melacak jejak lowongan via Yahoo: {query}")
        url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.find_all('div', class_='compTitle') + soup.find_all('div', class_='compText')
                for r in results:
                    text = r.get_text(separator=' ', strip=True)
                    if "@" in text or "hiring" in text.lower():
                        posts_text.append(text)
        except Exception as e:
            print(f"⚠️ Gangguan sinyal internet: {e}")
            
        if posts_text:
            print(f"✅ Ditemukan {len(posts_text)} potensi lowongan murni dari internet!")
            break

    # Mode Fallback Simulasi
    if not posts_text:
        print("⚠️ Peringatan: IP Server GitHub sedang dibatasi oleh mesin pencari.")
        print("🔄 Mengaktifkan Mode Simulasi: Surat lamaran akan dikirim ke email Anda sendiri untuk pengecekan perakitan AI...")
        posts_text = [
            f"WE ARE HIRING! PT Eksekusi Sukses mencari {posisi} di {lokasi}. "
            f"Please send your CV to: {user_email} "
        ]
        
    return posts_text

def send_to_log(webhook_url, perusahaan, email, skor, status):
    if not webhook_url: return
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        requests.post(webhook_url, json={"tanggal": now, "perusahaan": perusahaan, "email": email, "skor": skor, "status": status}, timeout=5)
    except:
        pass

def main():
    print("🤖 Bot LinkedIn CV Blaster Memulai Tugas...")
    
    config_url = os.environ.get("CONFIG_SHEET_URL")
    profile_url = os.environ.get("PROFILE_SHEET_URL")
    webhook_url = os.environ.get("LOG_WEBHOOK_URL")
    user_gmail = os.environ.get("GMAIL_USER")
    
    df_config = pd.read_csv(config_url)
    df_profile = pd.read_csv(profile_url)
    df_config.columns, df_profile.columns = df_config.columns.str.strip(), df_profile.columns.str.strip()
    
    config = dict(zip(df_config.iloc[:, 0].astype(str).str.strip(), df_config.iloc[:, 1].astype(str).str.strip()))
    profile = dict(zip(df_profile.iloc[:, 0].astype(str).str.strip(), df_profile.iloc[:, 1].astype(str).str.strip()))
    
    posisi = config.get("posisi", "Digital Marketing")
    lokasi = config.get("lokasi", "Jakarta")
    eligible_mode = str(config.get("eligible_mode", "ON")).upper()
    max_send = int(float(config.get("max_send_per_run", 5)))
    action_mode = str(config.get("action_mode", "send")).lower()
    
    print(f"📊 Konfigurasi -> Posisi: [{posisi}] | Lokasi: [{lokasi}] | Mode: [{action_mode}]")
    
    real_posts = search_realtime_posts(posisi, lokasi, user_gmail)
    sent_count = 0
    
    for post in real_posts:
        if sent_count >= max_send: break
        
        prompt = f"""
        Analisis teks postingan lowongan kerja berikut:
        "{post}"
        
        Profil Pelamar:
        - Nama: {profile.get('nama_lengkap')}
        - Skill: {profile.get('ringkasan_skill')}
        - Link Portfolio & CV: {profile.get('gdrive_folder_cv')}
        - LinkedIn: {profile.get('linkedin_url')}
        
        Tugas Anda:
        1. Ekstrak Nama Perusahaan.
        2. Ekstrak Email tujuan HR (Wajib cari yang pakai simbol @).
        3. Buat skor kecocokan (0-100).
        4. Tulis body email lamaran (Cover Letter) yang menawan dan profesional, WAJIB sertakan Link Portfolio/CV.
        
        Format WAJIB (Harus persis seperti ini):
        PERUSAHAAN: [nama]
        EMAIL: [email_hr]
        SUBJECT: Application for {posisi} - {profile.get('nama_lengkap')}
        SKOR: [skor]
        BODY: [isi_email]
        """
        
        try:
            response = model.generate_content(prompt)
            ai_output = response.text
        except Exception as e:
            print(f"❌ Gemini API Error: {e}")
            continue
        
        try:
            lines = ai_output.split('\n')
            nama_pt, email_hr, subject_email, score, body_email = "Perusahaan LinkedIn", "", f"Application for {posisi}", 100, ""
            
            for line in lines:
                if line.startswith("PERUSAHAAN:"): nama_pt = line.replace("PERUSAHAAN:", "").strip()
                elif line.startswith("EMAIL:"): email_hr = line.replace("EMAIL:", "").strip()
                elif line.startswith("SUBJECT:"): subject_email = line.replace("SUBJECT:", "").strip()
                elif line.startswith("SKOR:"): 
                    try: score = int(''.join(filter(str.isdigit, line)))
                    except: score = 85
                elif line.startswith("BODY:"):
                    body_email = ai_output.split("BODY:")[1].strip()
                    break
                    
            if not email_hr or "@" not in email_hr:
                print("⚠️ Gagal menemukan alamat email di postingan ini.")
                continue
                
            sender_password = os.environ.get("GMAIL_APP_PASSWORD")
            msg = EmailMessage()
            msg['Subject'], msg['From'], msg['To'] = subject_email, user_gmail, email_hr
            msg.set_content(body_email)
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(user_gmail, sender_password)
                if action_mode == "send":
                    smtp.send_message(msg)
                    status_str = "Terkirim (Sent)"
                else:
                    smtp.sendmail(user_gmail, [user_gmail], msg.as_string())
                    status_str = "Draft/Arsip"
                    
            print(f"✅ Sukses! Surat lamaran telah diterbangkan ke: {email_hr} [{status_str}]")
            send_to_log(webhook_url, nama_pt, email_hr, score, status_str)
            sent_count += 1
            
        except Exception as e:
            print(f"❌ Error merakit email: {e}")

if __name__ == "__main__":
    main()
