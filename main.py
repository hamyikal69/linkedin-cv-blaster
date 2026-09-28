import os
import smtplib
from email.message import EmailMessage
import pandas as pd
import google.generativeai as genai

AI_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=AI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def main():
    print("Bot LinkedIn CV Blaster Memulai Tugas di Cloud...")
    
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
    
    print(f"Target Keyword: {keyword} | Mode Eligible: {eligible_mode} | Max Kirim: {max_send}")
    
    sample_posts = [
        "Dibutuhkan segera Data Analyst untuk penempatan Jakarta. Kualifikasi: Menguasai SQL, Python, dan Looker Studio, pengalaman min 1 tahun. Kirim CV dan portofolio Anda ke hrd.data@perusahaanmaju.com dengan subjek 'Lamaran Data Analyst - Nama'. Ditunggu segera!",
        "We are looking for a passionate Marketing Intern! Send your resume to career@agatedigital.id. Subject: Internship Marketing."
    ]
    
    sent_count = 0
    for post in sample_posts:
        if sent_count >= max_send:
            break
            
        print("\nMenganalisis postingan HR...")
        prompt = f"""
        Analisis teks postingan LinkedIn HR berikut:
        "{post}"
        
        Profil Pelamar:
        - Nama: {profile.get('nama_lengkap')}
        - Skill: {profile.get('ringkasan_skill')}
        - Link Portfolio & GDrive: {profile.get('gdrive_folder_cv')}
        - LinkedIn: {profile.get('linkedin_url')}
        
        Aturan Mode Eligible: {eligible_mode}
        
        Tugas Anda:
        1. Ekstrak Email tujuan HR dan Subjek Email yang disarankan.
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
                    
            if not email_hr or "@" not in email_hr:
                continue
                
            if eligible_mode == "ON" and score < 70:
                print(f"Melewatkan lowongan karena Skor AI ({score}) di bawah batas 70.")
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
                    print(f"BERHASIL DIKIRIM ke {email_hr}!")
                else:
                    smtp.sendmail(sender_email, [sender_email], msg.as_string())
                    print(f"Disimpan ke Draft/Arsip.")
                    
            sent_count += 1
        except Exception as e:
            print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    main()
