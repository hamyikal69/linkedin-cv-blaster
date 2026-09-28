import os
import smtplib
from email.message import EmailMessage
import urllib.parse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import google.generativeai as genai

AI_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel('gemini-3.5-flash-lite')

def search_realtime_posts(keyword):
    """Fungsi untuk mencari postingan publik LinkedIn secara real-time di internet"""
    print(f"🌐 Sedang mencari lowongan real-time untuk keyword: '{keyword}'...")
    query = f"site:linkedin.com/posts/ {keyword} hiring email"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    posts_text = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Mengambil cuplikan teks hasil pencarian yang berisi info lowongan
            results = soup.find_all('a', class_='result__snippet')
            for r in results:
                posts_text.append(r.get_text())
    except Exception as e:
        print(f"⚠️ Gagal mengambil data internet: {e}")
        
    return posts_text

def main():
    print("🤖 Bot LinkedIn CV Blaster Memulai Tugas Real-Time di Cloud...")
    
    config_url = os.environ.get("CONFIG_SHEET_URL")
    profile_url = os.environ.get("PROFILE_SHEET_URL")
    
    df_config = pd.read_csv(config_url)
    df_profile = pd.read_csv(profile_url)
    
    config = dict(zip(df_config.iloc[:, 0], df_config.iloc[:, 1]))
    profile = dict(zip(df_profile.iloc[:, 0], df_profile.iloc[:, 1]))
    
    keyword = config.get("keyword", "Data Analyst hiring email")
    eligible_mode = str(config.get("eligible_mode", "ON")).upper()
    max_send = int(config.get("max_send_per_run", 5))
    action_mode = str(config.get("action_mode", "send")).lower()
    
    print(f"🎯 Target Keyword: {keyword} | Mode Eligible: {eligible_mode} | Max Kirim: {max_send}")
    
    # Ambil data postingan nyata dari internet secara real-time
    real_posts = search_realtime_posts(keyword)
    
    if not real_posts:
        print("❌ Tidak ditemukan postingan lowongan baru saat ini. Coba ganti kata kunci di Google Sheets.")
        return
        
    print(f"✨ Berhasil menemukan {len(real_posts)} cuplikan postingan untuk dianalisis.")
    sent_count = 0
    
    for post in real_posts:
        if sent_count >= max_send:
            break
            
        print("\n-----------------------------------------")
        print("🧠 Menganalisis postingan dengan AI...")
        prompt = f"""
        Analisis cuplikan teks postingan LinkedIn berikut:
        "{post}"
        
        Profil Pelamar:
        - Nama: {profile.get('nama_lengkap')}
        - Skill: {profile.get('ringkasan_skill')}
        - Link Portfolio & GDrive: {profile.get('gdrive_folder_cv')}
        - LinkedIn: {profile.get('linkedin_url')}
        
        Aturan Mode Eligible: {eligible_mode}
        
        Tugas Anda:
        1. Ekstrak Email tujuan HR (jika ada di teks). Jika tidak ada email sama sekali, tulis EMAIL: TIDAK_ADA.
        2. Jika Mode Eligible 'ON', berikan penilaian skor kecocokan (0 sampai 100) antara skill pelamar dengan postingan.
        3. Buat body email lamaran profesional yang ramah, persuasif, dan menyertakan link folder GDrive pelamar.
        
        Berikan jawaban dalam format teks bersih dengan pemisah berikut:
        EMAIL: [email_hr]
        SUBJECT: [subjek_email]
        SKOR: [angka_skor]
        BODY: [isi_surat_lamaran]
        """
        
        response = model.generate_content(prompt)
        ai_output = response.text
        
        try:
            lines = ai_output.split('\n')
            email_hr = ""
            subject_email = "Lamaran Pekerjaan"
            score = 100
            body_email = ""
            
            for line in lines:
                if line.startswith("EMAIL:"):
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
                print("⚠️ Postingan ini dilewati karena tidak mencantumkan alamat email HR yang valid.")
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
                    print(f"✅ BERHASIL DIKIRIM otomatis ke {email_hr}!")
                else:
                    smtp.sendmail(sender_email, [sender_email], msg.as_string())
                    print(f"📝 Disimpan ke Draft/Arsip.")
                    
            sent_count += 1
        except Exception as e:
            print(f"❌ Terjadi kesalahan: {e}")

if __name__ == "__main__":
    main()
