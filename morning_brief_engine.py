import os
import datetime
import pytz
import google.generativeai as genai
from string import Template

# --- CONFIGURATION ---
# You need a Gemini API Key (Get one at aistudio.google.com)
API_KEY = os.environ.get("GEMINI_API_KEY") 
TIMEZONE = "Asia/Qatar"
USER_BIRTH_DATA = "14 Haziran 1989, 09:45 AM, Fatih, Istanbul"

# --- THE HTML TEMPLATE ---
# We use Python's Template string for safer substitution than f-strings with all these CSS braces
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
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
        * { box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }
        body { background-color: var(--bg-body); color: var(--text-main); font-family: var(--font-stack); margin: 0; padding: 0; line-height: 1.5; font-size: 16px; overflow-x: hidden; min-height: 100vh; }
        .container { max-width: 480px; margin: 0 auto; padding: 0 0 40px 0; }
        .header-graphic { width: 100%; height: 180px; background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%); display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; border-bottom: 1px solid #333; }
        .header-content { position: absolute; bottom: 20px; left: 20px; z-index: 2; }
        .date-badge { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); padding: 4px 10px; border-radius: 8px; font-size: 0.8rem; color: var(--accent-primary); font-weight: 600; display: inline-block; margin-bottom: 5px; }
        h1 { margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; }
        .toc-scroller { position: sticky; top: 0; background: rgba(5, 5, 5, 0.95); backdrop-filter: blur(10px); z-index: 100; padding: 10px 0; white-space: nowrap; overflow-x: auto; border-bottom: 1px solid #222; display: flex; gap: 10px; padding-left: 15px; scrollbar-width: none; }
        .toc-scroller::-webkit-scrollbar { display: none; }
        .toc-link { color: var(--text-muted); text-decoration: none; font-size: 0.85rem; font-weight: 600; padding: 6px 12px; border-radius: 20px; background: var(--bg-card); transition: all 0.2s; border: 1px solid #333; }
        .toc-link:hover, .toc-link.active { color: var(--bg-body); background: var(--text-main); border-color: var(--text-main); }
        .section-wrapper { padding: 20px 15px 0 15px; }
        .card { background-color: var(--bg-card); border-radius: var(--border-radius); padding: 20px; margin-bottom: 20px; border: 1px solid #222; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
        .card-title { font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        .tag { font-size: 0.7rem; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; font-weight: 700; letter-spacing: 0.5px; }
        .tag-blue { background: rgba(135, 206, 235, 0.15); color: var(--accent-secondary); }
        .tag-gold { background: rgba(255, 215, 0, 0.15); color: var(--accent-primary); }
        .tag-red { background: rgba(255, 107, 107, 0.15); color: var(--accent-danger); }
        .tag-green { background: rgba(78, 205, 196, 0.15); color: var(--accent-success); }
        p { margin-bottom: 12px; font-size: 0.95rem; color: #ccc; }
        p:last-child { margin-bottom: 0; }
        ul.bullet-list { list-style: none; padding: 0; margin: 0; }
        ul.bullet-list li { position: relative; padding-left: 20px; margin-bottom: 10px; font-size: 0.95rem; color: #d0d0d0; }
        ul.bullet-list li::before { content: "•"; position: absolute; left: 0; color: var(--accent-secondary); font-weight: bold; }
        .visual-mood { height: 60px; border-radius: 12px; background: $mood_gradient; margin-bottom: 15px; position: relative; }
        .visual-mood::after { content: "$mood_text"; position: absolute; right: 10px; bottom: 5px; font-size: 0.7rem; color: rgba(255,255,255,0.7); }
        .decision-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 10px; }
        .decision-box { background: var(--bg-card-highlight); padding: 10px 5px; border-radius: 10px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .d-icon { font-size: 1.2rem; margin-bottom: 4px; }
        .d-label { font-size: 0.7rem; color: var(--text-muted); font-weight: 600; }
        .d-val { font-size: 0.8rem; font-weight: 700; margin-top: 2px; }
        .d-good { color: var(--accent-success); }
        .d-bad { color: var(--accent-danger); }
        .d-neutral { color: var(--text-muted); }
        .ticker-pill { display: inline-block; background: #2A2A2A; border: 1px solid #444; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-size: 0.85rem; color: var(--accent-primary); margin-right: 4px; }
        .footer { text-align: center; padding: 30px 20px; font-size: 0.8rem; color: #555; border-top: 1px solid #222; margin-top: 20px; }
    </style>
</head>
<body>
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
        
        <div class="footer">
            <p>Okuma süresi: ~2-3 dk</p>
            <p style="opacity: 0.5;">Generated automatically for Fatih</p>
        </div>
    </div>
</body>
</html>
""")

def get_current_date_qatar():
    qatar_tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(qatar_tz)
    # Format: 28 Ocak 2026, Çarşamba
    months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return f"{now.day} {months[now.month]} {now.year}, {days[now.weekday()]}"

def generate_daily_brief():
    if not API_KEY:
        print("Error: GEMINI_API_KEY not found.")
        return

    genai.configure(api_key=API_KEY)
    
    date_str = get_current_date_qatar()
    print(f"Generating brief for: {date_str}...")

    # The Prompt - We ask for HTML fragments only to inject into our template
    prompt = f"""
    Sen kişisel bir astroloji ve finans asistanısın.
    Tarih: {date_str} (Zaman dilimi: Asia/Qatar).
    Kullanıcı: Fatih (Doğum: {USER_BIRTH_DATA}).
    Güneş: İkizler, Ay: Terazi, Yükselen: Aslan.
    
    Görevin: Aşağıdaki HTML şablonuna uygun "body" içeriğini (header ve footer HARIÇ) üretmek.
    
    Kurallar:
    1. YANIT SADECE HTML OLMALI. ```html``` bloğu içinde olmalı.
    2. Header veya <html> tagleri koyma. Sadece <div class="section-wrapper">...</div> bloklarını üret.
    3. Aşağıdaki bölümleri üret:
       - Odak Çapası (3 kelime kuralı ile)
       - Dün -> Bugün (Mood analizi)
       - Horoskop (Aslan Yükselen + İkizler Güneş odaklı, transitlere göre)
       - Karar Zaman Haritası (Karar tablosu HTML'i)
       - İş & Kariyer
       - Para & Finans (Whitelist: QQQI, FDVV, SCHD, SCHG, IAUI, SLV. Blacklist: YMAG, TQQQ)
       - İlişkiler
       - Tek Soru
    
    Stil Notları:
    - Finans kısmında "Genel piyasa haberi" verme. Fatih'in portföyü için "TUT", "EKLE" veya "BEKLE" gibi net emirler ver.
    - Karar Haritası için <div class="decision-grid"> yapısını kullan.
    - Emoji kullanımı bol olsun.
    - Dark mode uyumlu renkler kullanılmış varsay.
    """

    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    
    # Extract text and clean up markdown code blocks if present
    raw_html = response.text.replace("```html", "").replace("```", "").strip()
    
    # Extract Mood Logic (Simple randomizer or parsed from text could go here)
    # For now, we hardcode a dynamic gradient based on the text length or hash to vary it daily
    mood_gradients = [
        "linear-gradient(90deg, #2c3e50 0%, #3498db 50%, #f1c40f 100%)",
        "linear-gradient(90deg, #1a2980 0%, #26d0ce 100%)",
        "linear-gradient(90deg, #8E2DE2 0%, #4A00E0 100%)",
        "linear-gradient(90deg, #f12711 0%, #f5af19 100%)"
    ]
    daily_mood_gradient = mood_gradients[datetime.datetime.now().day % 4]
    
    # Assemble final HTML
    final_html = HTML_TEMPLATE.substitute(
        date_string=date_str,
        content_body=raw_html,
        mood_gradient=daily_mood_gradient,
        mood_text="Günlük Enerji Akışı"
    )

    # Save to file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    print("Success! index.html updated.")

if __name__ == "__main__":
    generate_daily_brief()
