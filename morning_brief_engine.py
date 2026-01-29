import os
import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from string import Template

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
TIMEZONE = "Asia/Qatar"
USER_BIRTH_DATA = "14 Haziran 1989, 09:45 AM, Fatih, Istanbul"

# Email Config
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO")

# --- THE HTML TEMPLATE ---
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <!-- FORCE NO CACHE -->
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Morning Brief | Fatih</title>
    <style>
        :root {
            --bg-body: #050505; --bg-card: #141414; --bg-card-highlight: #1F1F1F;
            --text-main: #E0E0E0; --text-muted: #A0A0A0;
            --accent-primary: #FFD700; --accent-secondary: #87CEEB;
            --accent-danger: #FF6B6B; --accent-success: #4ECDC4;
            --border-radius: 16px;
            --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        body { background-color: #050505; color: #E0E0E0; font-family: Helvetica, Arial, sans-serif; margin: 0; padding: 0; }
        .container { max-width: 480px; margin: 0 auto; padding: 20px; }
        .card { background-color: #141414; border-radius: 16px; padding: 20px; margin-bottom: 20px; border: 1px solid #222; }
        .tag { font-size: 12px; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; font-weight: bold; background: #333; color: #fff; display: inline-block;}
        h1 { margin: 0; font-size: 24px; color: #fff; }
        p { color: #ccc; line-height: 1.5; }
        .d-good { color: #4ECDC4; font-weight: bold; }
        .d-bad { color: #FF6B6B; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align:center; padding-bottom: 20px; border-bottom: 1px solid #333;">
            <div style="font-size: 14px; color: #FFD700; font-weight: bold;">📅 $date_string</div>
            <h1>Günaydın, Fatih.</h1>
        </div>
        
        <!-- AI GENERATED CONTENT -->
        $content_body
        
        <div style="text-align: center; margin-top: 30px; font-size: 11px; color: #555;">
            Generated: $gen_time (Qatar Time)<br>
            Sent from your GitHub Robot 🤖
        </div>
    </div>
</body>
</html>
""")

def get_current_time_qatar():
    qatar_tz = pytz.timezone(TIMEZONE)
    return datetime.datetime.now(qatar_tz)

def format_date_str(now):
    months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return f"{now.day} {months[now.month]} {now.year}, {days[now.weekday()]}"

def send_email(html_content, date_str):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_TO:
        print("Skipping email: Credentials not found.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Morning Brief: {date_str}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def generate_daily_brief():
    if not API_KEY:
        print("Error: GEMINI_API_KEY not found.")
        return

    genai.configure(api_key=API_KEY)
    
    # Get precise time
    now_qatar = get_current_time_qatar()
    date_str = format_date_str(now_qatar)
    gen_time_str = now_qatar.strftime("%H:%M:%S")

    print(f"Generating brief for: {date_str} at {gen_time_str}...")

    prompt = f"""
    Sen kişisel bir astroloji ve finans asistanısın.
    Tarih: {date_str} (Zaman dilimi: Asia/Qatar).
    Kullanıcı: Fatih (Doğum: {USER_BIRTH_DATA}).
    Güneş: İkizler, Ay: Terazi, Yükselen: Aslan.
    
    HTML şablonuna uygun "body" içeriği üret.
    Sadece <div class="card">...</div> bloklarını üret. Header/Footer/HTML tagleri koyma.
    
    Bölümler:
    1. Odak (3 kelime)
    2. Dün->Bugün
    3. Horoskop (Aslan Yükselen/İkizler Güneş)
    4. İş & Kariyer
    5. Finans (Whitelist: QQQI, FDVV, SCHD, SCHG, IAUI, SLV) - Net "TUT/EKLE" emirleri ver.
    """

    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    raw_html = response.text.replace("```html", "").replace("```", "").strip()
    
    final_html = HTML_TEMPLATE.substitute(
        date_string=date_str,
        content_body=raw_html,
        gen_time=gen_time_str
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    send_email(final_html, date_str)

if __name__ == "__main__":
    generate_daily_brief()
