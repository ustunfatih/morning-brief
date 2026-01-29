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

# --- THE HTML TEMPLATE (PREMIUM RESTORED) ---
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <!-- CACHE BUSTING -->
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

        /* Reset & Base */
        * { box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }
        body {
            background-color: var(--bg-body);
            color: var(--text-main);
            font-family: var(--font-stack);
            margin: 0;
            padding: 0;
            line-height: 1.5;
            font-size: 16px;
            min-height: 100vh;
        }

        /* Layout Container */
        .container {
            max-width: 480px;
            margin: 0 auto;
            padding: 0 0 40px 0;
        }

        /* Header Graphic */
        .header-graphic {
            width: 100%;
            height: 180px;
            background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
            border-bottom: 1px solid #333;
        }
        .header-content {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 2;
        }
        .date-badge {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.8rem;
            color: var(--accent-primary);
            font-weight: 600;
            display: inline-block;
            margin-bottom: 5px;
        }
        h1 { margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; }
        
        /* Navigation (TOC) */
        .toc-scroller {
            position: sticky;
            top: 0;
            background: rgba(5, 5, 5, 0.95);
            backdrop-filter: blur(10px);
            z-index: 100;
            padding: 10px 0;
            white-space: nowrap;
            overflow-x: auto;
            border-bottom: 1px solid #222;
            display: flex;
            gap: 10px;
            padding-left: 15px;
            scrollbar-width: none;
        }
        .toc-scroller::-webkit-scrollbar { display: none; }
        .toc-link {
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 20px;
            background: var(--bg-card);
            transition: all 0.2s;
            border: 1px solid #333;
        }
        .toc-link:hover, .toc-link.active {
            color: var(--bg-body);
            background: var(--text-main);
            border-color: var(--text-main);
        }

        /* Sections */
        .section-wrapper { padding: 20px 15px 0 15px; }

        /* Cards */
        .card {
            background-color: var(--bg-card);
            border-radius: var(--border-radius);
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #222;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .tag {
            font-size: 0.7rem;
            text-transform: uppercase;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .tag-blue { background: rgba(135, 206, 235, 0.15); color: var(--accent-secondary); }
        .tag-gold { background: rgba(255, 215, 0, 0.15); color: var(--accent-primary); }
        .tag-red { background: rgba(255, 107, 107, 0.15); color: var(--accent-danger); }
        .tag-green { background: rgba(78, 205, 196, 0.15); color: var(--accent-success); }

        /* Typography & Lists */
        p { margin-bottom: 12px; font-size: 0.95rem; color: #ccc; }
        p:last-child { margin-bottom: 0; }
        ul.bullet-list { list-style: none; padding: 0; margin: 0; }
        ul.bullet-list li {
            position: relative;
            padding-left: 20px;
            margin-bottom: 10px;
            font-size: 0.95rem;
            color: #d0d0d0;
        }
        ul.bullet-list li::before {
            content: "•";
            position: absolute;
            left: 0;
            color: var(--accent-secondary);
            font-weight: bold;
        }
        
        /* Visual Mood */
        .visual-mood {
            height: 60px;
            border-radius: 12px;
            background: linear-gradient(90deg, #2c3e50 0%, #3498db 50%, #f1c40f 100%);
            margin-bottom: 15px;
            position: relative;
        }

        /* Decision Map Grid */
        .decision-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin-top: 10px;
        }
        .decision-box {
            background: var(--bg-card-highlight);
            padding: 10px 5px;
            border-radius: 10px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .d-icon { font-size: 1.2rem; margin-bottom: 4px; }
        .d-label { font-size: 0.7rem; color: var(--text-muted); font-weight: 600; }
        .d-val { font-size: 0.8rem; font-weight: 700; margin-top: 2px; }
        .d-good { color: var(--accent-success); }
        .d-bad { color: var(--accent-danger); }
        .d-neutral { color: var(--text-muted); }

        /* Finance Pill */
        .ticker-pill {
            display: inline-block;
            background: #2A2A2A;
            border: 1px solid #444;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--accent-primary);
            margin-right: 4px;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 30px 20px;
            font-size: 0.8rem;
            color: #555;
            border-top: 1px solid #222;
            margin-top: 20px;
        }
        
        .status-bar {
            background: #111;
            color: #666;
            font-size: 10px;
            text-align: right;
            padding: 5px 10px;
            font-family: monospace;
            border-bottom: 1px solid #222;
        }
    </style>
</head>
<body>
    <div class="status-bar">SON GÜNCELLEME: $gen_time (Qatar)</div>

    <!-- Header -->
    <header class="header-graphic">
        <svg style="position: absolute; top:0; left:0; width:100%; height:100%; opacity: 0.3;" viewBox="0 0 100 100" preserveAspectRatio="none">
            <circle cx="20" cy="80" r="30" fill="#87CEEB" />
            <circle cx="80" cy="20" r="40" fill="#FFD700" />
            <path d="M0,50 Q50,0 100,50 T200,50" stroke="#4ECDC4" stroke-width="0.5" fill="none" />
        </svg>
        <div class="header-content">
            <div class="date-badge">📅 $date_string</div>
            <h1>Günaydın, Fatih.</h1>
            <div style="font-size: 0.9rem; color: #aaa; margin-top:4px;">📍 Doha, Katar</div>
        </div>
    </header>

    <!-- Navigation -->
    <nav class="toc-scroller">
        <a href="#odak" class="toc-link">Odak</a>
        <a href="#karar" class="toc-link">Karar</a>
        <a href="#is" class="toc-link">İş</a>
        <a href="#finans" class="toc-link">Finans</a>
        <a href="#astro" class="toc-link">Astro</a>
    </nav>

    <div class="container">
        <!-- AI GENERATED CONTENT INJECTED HERE -->
        $content_body
        
        <!-- Footer -->
        <div class="footer">
            <p>Okuma süresi: ~2.5 dk</p>
            <p style="opacity: 0.5;">© 2026 Morning Brief - Fatih</p>
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

    # We send the rich HTML. Email clients may strip some CSS, but the content will be full.
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
    
    # Time Calc
    now_qatar = get_current_time_qatar()
    date_str = format_date_str(now_qatar)
    gen_time_str = now_qatar.strftime("%H:%M:%S")

    print(f"Generating brief for: {date_str}...")

    # --- RESTORED DETAILED PROMPT ---
    prompt = f"""
    Sen Fatih için "Morning Brief" hazırlayan, çok zeki ve biraz da esprili bir astroloji & finans asistanısın.
    
    PARAMETRELER:
    - Tarih: {date_str} (Zaman dilimi: Asia/Qatar).
    - Kullanıcı: Fatih (Doğum: {USER_BIRTH_DATA}).
    - Astro Kimlik: Güneş İkizler, Ay Terazi, Yükselen Aslan.
    - Dil: Türkçe.
    - Ton: Kısa, net, bullet-point ağırlıklı. Mobil öncelikli.
    
    PORTFÖY İZLEME LISTESI (Whitelist): QQQI, FDVV, SCHD, SCHG, IAUI, SLV.
    YASAKLI LISTE (Blacklist): YMAG, TQQQ, GLDW.
    
    GÖREV:
    Aşağıdaki HTML yapısına BİREBİR uyarak sadece BODY içeriğini (header/footer hariç) üret.
    Her bölümü <div class="section-wrapper" id="...">...</div> içine al.
    
    İSTENEN BÖLÜMLER VE HTML YAPISI:
    
    1. ODAK ÇAPASI (ID: odak):
       - <div class="card" style="border-left: 4px solid var(--accent-primary);"> kullan.
       - İçinde bir Motto ve "3 Kelime Kuralı" olsun.
    
    2. DÜN -> BUGÜN & MOOD:
       - <div class="visual-mood"></div> div'ini mutlaka koy (CSS ile renkleniyor).
       - Kısa bir ruh hali geçiş analizi yap.
    
    3. HOROSKOP (ID: astro):
       - Aslan Yükselen ve Kova/İkizler transitlerine odaklan.
       - <span class="tag tag-blue"> gibi renkli etiketler kullan.
       - "Astro-Bilişsel Uyarı" başlığı altında bir <div class="card" style="background: #1a1515;"> ekle.
    
    4. KARAR ZAMAN HARİTASI (ID: karar):
       - MUTLAKA şu grid yapısını kullan:
         <div class="decision-grid">
            <div class="decision-box">...Simge, EN İYİ, Eylem...</div>
            <div class="decision-box">...Simge, NÖTR, Eylem...</div>
            <div class="decision-box">...Simge, KAÇIN, Eylem...</div>
         </div>
    
    5. İŞ & KARİYER (ID: is):
       - Bullet list kullan (<ul class="bullet-list">).
       - Yükselen Aslan liderliği ile İkizler zekasını birleştir.
    
    6. FİNANS (ID: finans):
       - Genel piyasa haberi VERME.
       - Fatih'in Whitelist'indeki hisseler için (QQQI, SCHD vs.) somut "Davranışsal Notlar" yaz.
       - Hisse adlarını <span class="ticker-pill">HİSSE</span> şeklinde yaz.
    
    7. TEK SORU:
       - Günün düşündürücü sorusu.
    
    ÖNEMLİ KURALLAR:
    - Asla ```html``` bloğu koyma, sadece saf HTML kodu döndür.
    - Asla <html>, <head>, <body> taglerini açma.
    - Dark mode uyumlu ol (zaten CSS hallediyor, sen class'ları doğru kullan).
    """

    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    
    # Temizlik
    raw_html = response.text.replace("```html", "").replace("```", "").strip()
    
    # Template Birleştirme
    final_html = HTML_TEMPLATE.substitute(
        date_string=date_str,
        content_body=raw_html,
        gen_time=gen_time_str
    )

    # 1. Dosyaya Yaz (Web İçin)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    # 2. Email Gönder
    send_email(final_html, date_str)

if __name__ == "__main__":
    generate_daily_brief()
