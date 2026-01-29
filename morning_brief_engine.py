import os
import datetime
import pytz
import smtplib
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from string import Template
from kerykeion import AstrologicalSubjectFactory
import yfinance as yf

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
TIMEZONE = "Asia/Qatar"
USER_BIRTH_DATA = "14 Haziran 1989, 09:45 AM, Fatih, Istanbul"
CACHE_DIR = ".cache"

# Fatih's natal chart coordinates (Istanbul, Fatih district)
NATAL_YEAR, NATAL_MONTH, NATAL_DAY = 1989, 6, 14
NATAL_HOUR, NATAL_MINUTE = 9, 45
NATAL_LAT, NATAL_LNG = 41.0082, 28.9784  # Istanbul
NATAL_TZ = "Europe/Istanbul"

# Doha coordinates (current location)
DOHA_LAT, DOHA_LNG = 25.2854, 51.5310
DOHA_TZ = "Asia/Qatar"

# --- ASTROLOGER REFERENCES ---
ASTROLOGER_SOURCES = """
TÜRK ASTROLOGLAR:
- Dinçer Güner: YouTube https://www.youtube.com/channel/UCe5FpvalDw47kRWNxVVlRjQ | X/Twitter https://x.com/dincerguner | Instagram https://www.instagram.com/dincerguner/ | Web https://www.dincerguner.com/
- Hande Kazanova: YouTube https://www.youtube.com/channel/UCKC-ZB0pXPRB44ekCT6nCzA | X/Twitter https://x.com/Hande_Kazanova | Instagram https://www.instagram.com/handekazanova/
- Öner Döşer: YouTube https://www.youtube.com/channel/UCpr1OfHZ2tYPl3nFbwPGMsg | X/Twitter https://x.com/oner_doser | Instagram https://www.instagram.com/onerdoser/ | Web https://www.onerdoser.com/
- Can Aydoğmuş: YouTube https://www.youtube.com/@canaydogmus | X/Twitter https://x.com/SizisevenbirCan | Instagram https://www.instagram.com/canyaziyor/ | Web https://www.canaydogmus.com.tr/

ULUSLARARASI ASTROLOGLAR:
- Chani Nicholas: X/Twitter https://x.com/chaninicholas | Instagram https://www.instagram.com/chaninicholas/ | Web/App https://www.chani.com/
- The AstroTwins (Ophira & Tali Edut): X/Twitter https://x.com/astrotwins | Instagram https://www.instagram.com/astrotwins/ | Web https://astrostyle.com/
- Susan Miller (Astrology Zone): X/Twitter https://x.com/astrologyzone | Instagram https://www.instagram.com/astrologyzone/ | Web https://www.astrologyzone.com/
- Co-Star Astrology: X/Twitter https://twitter.com/costarastrology | Instagram https://www.instagram.com/costarastrology/ | Web https://www.costarastrology.com/
"""

ASTROLOGY_BOOKS = """
REFERANS KİTAPLAR:
- "The Only Astrology Book You'll Ever Need" - Joanna Martine Woolfolk
- "Astrology for the Soul" - Jan Spiller (Ay Düğümleri rehberi)
- "The Inner Sky" - Steven Forrest (Modern psikolojik astroloji)
- "Parker's Astrology" - Julia & Derek Parker (Kapsamlı başvuru kitabı)
- "Yükselen Burcunuzu Tanıyın" - Öner Döşer
- "Astroloji: Kendini Bil" - Hande Kazanova
"""

# Email Config
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO")

# --- THE HTML TEMPLATE (RESPONSIVE HEADER FIXED) ---
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
            --bg-body: #FDF6EC; --bg-card: #FFFFFF; --bg-card-highlight: #FFF8F0;
            --text-main: #3D3D3D; --text-muted: #7A7A7A;
            --accent-primary: #E8A87C; --accent-secondary: #A8D8EA;
            --accent-danger: #F3A6A6; --accent-success: #A8E6CF;
            --accent-lavender: #C3B1E1;
            --border-radius: 16px;
            --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --shadow-card: 0 2px 12px rgba(0,0,0,0.06);
            --border-light: #E8DFD4;
        }

        /* Reset & Base */
        * { box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }
        body {
            background-color: var(--bg-body);
            color: var(--text-main);
            font-family: var(--font-stack);
            margin: 0;
            padding: 0;
            line-height: 1.6;
            font-size: 0.95rem;
            min-height: 100vh;
        }

        /* Layout Container */
        .container {
            max-width: 480px;
            margin: 0 auto;
            padding: 0 0 24px 0;
        }

        /* Header Graphic - RESPONSIVE */
        .header-wrapper {
            background-color: var(--bg-body);
            width: 100%;
            display: flex;
            justify-content: center;
        }

        .header-graphic {
            width: 100%;
            max-width: 480px;
            height: 180px;
            background: linear-gradient(135deg, #FFF1E6 0%, #E8F4FD 50%, #F3E8FF 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
            border-bottom: 1px solid var(--border-light);
            border-radius: 0 0 24px 24px;
        }

        .header-content {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 2;
        }
        .date-badge {
            background: rgba(232, 168, 124, 0.15);
            backdrop-filter: blur(10px);
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.8rem;
            color: #C07A50;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 5px;
        }
        h1 { margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; color: #3D3D3D; }

        /* Mood Band - thin decorative strip */
        .mood-band {
            height: 6px;
            width: 100%;
            background: linear-gradient(90deg, var(--accent-lavender) 0%, var(--accent-secondary) 35%, var(--accent-success) 65%, var(--accent-primary) 100%);
            margin: 0;
            border: none;
        }

        /* Navigation (TOC) */
        .toc-scroller {
            position: sticky;
            top: 0;
            background: rgba(253, 246, 236, 0.95);
            backdrop-filter: blur(10px);
            z-index: 100;
            padding: 10px 0;
            white-space: nowrap;
            overflow-x: auto;
            border-bottom: 1px solid var(--border-light);
            display: flex;
            gap: 10px;
            justify-content: center;
            scrollbar-width: none;
        }
        .toc-progress {
            position: sticky;
            top: 46px;
            height: 3px;
            background: rgba(232, 168, 124, 0.15);
            z-index: 99;
        }
        .toc-progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            transition: width 0.1s linear;
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
            border: 1px solid var(--border-light);
        }
        .toc-link:hover, .toc-link.active {
            color: #FFFFFF;
            background: var(--accent-primary);
            border-color: var(--accent-primary);
        }
        .toc-link:focus-visible {
            outline: 2px solid #C07A50;
            outline-offset: 2px;
        }

        /* Sections */
        .section-wrapper { padding: 12px 15px 0 15px; scroll-margin-top: 72px; }

        /* Cards */
        .card {
            background-color: var(--bg-card);
            border-radius: var(--border-radius);
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid var(--border-light);
            box-shadow: var(--shadow-card);
        }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .card-title {
            font-size: 1rem;
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
        .tag-blue { background: rgba(168, 216, 234, 0.25); color: #5B9BB5; }
        .tag-gold { background: rgba(232, 168, 124, 0.2); color: #C07A50; }
        .tag-red { background: rgba(243, 166, 166, 0.25); color: #C07070; }
        .tag-green { background: rgba(168, 230, 207, 0.3); color: #5DAE8B; }
        .tag-lavender { background: rgba(195, 177, 225, 0.25); color: #8B72B2; }

        /* Typography & Lists */
        p { margin-bottom: 10px; font-size: 0.95rem; color: #555; }
        p:last-child { margin-bottom: 0; }
        h2, h3, h4 { font-size: 1.1rem; margin: 0 0 8px 0; }
        ul.bullet-list { list-style: none; padding: 0; margin: 0; }
        ul.bullet-list li {
            position: relative;
            padding-left: 18px;
            margin-bottom: 8px;
            font-size: 0.95rem;
            color: #4A4A4A;
        }
        ul.bullet-list li::before {
            content: "•";
            position: absolute;
            left: 0;
            color: var(--accent-secondary);
            font-weight: bold;
        }

        /* Weather Card */
        .weather-card {
            background: linear-gradient(135deg, #E8F4FD 0%, #F0EAFF 100%);
            border-radius: var(--border-radius);
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid #D4E8F0;
            box-shadow: var(--shadow-card);
            position: relative;
        }
        .weather-card .weather-icon-wrap {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
        }
        .weather-card .weather-icon-wrap svg {
            flex-shrink: 0;
        }
        .weather-card .weather-summary {
            font-size: 0.85rem;
            color: #4A4A4A;
        }
        .weather-card .weather-summary strong {
            color: #3D3D3D;
        }
        .weather-periods {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin-top: 10px;
        }
        .weather-period {
            background: rgba(255,255,255,0.7);
            border-radius: 10px;
            padding: 10px 8px;
            text-align: center;
            font-size: 0.85rem;
            color: #4A4A4A;
        }
        .weather-period strong {
            display: block;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
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
            border: 1px solid var(--border-light);
        }
        .d-icon { font-size: 1.2rem; margin-bottom: 4px; }
        .d-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }
        .d-val { font-size: 0.85rem; font-weight: 700; margin-top: 2px; }
        .d-good { color: var(--accent-success); }
        .d-bad { color: var(--accent-danger); }
        .d-neutral { color: var(--text-muted); }

        /* Finance Pill */
        .ticker-pill {
            display: inline-block;
            background: rgba(232, 168, 124, 0.12);
            border: 1px solid rgba(232, 168, 124, 0.3);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
            color: #C07A50;
            margin-right: 4px;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 20px 15px;
            font-size: 0.8rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border-light);
            margin-top: 12px;
        }
        .data-freshness {
            font-size: 0.75rem;
            color: #9A8E82;
            margin-top: 6px;
        }

        .status-bar {
            background: #F5EDE3;
            color: #9A8E82;
            font-size: 10px;
            text-align: right;
            padding: 5px 10px;
            font-family: monospace;
            border-bottom: 1px solid var(--border-light);
        }

        /* Responsive: wider on desktop */
        @media (min-width: 768px) {
            .container, .header-graphic { max-width: 600px; }
        }
        @media (min-width: 1024px) {
            .container, .header-graphic { max-width: 680px; }
        }
        @media (max-width: 420px) {
            body { font-size: 0.92rem; }
            .weather-periods { grid-template-columns: 1fr; }
            .decision-grid { grid-template-columns: 1fr; }
            .card { padding: 14px; }
        }
    </style>
</head>
<body>
    <div class="status-bar">SON GÜNCELLEME: $gen_time (Qatar)</div>

    <!-- Header Wrapper to Center on Desktop -->
    <div class="header-wrapper">
        <header class="header-graphic">
            <svg style="position: absolute; top:0; left:0; width:100%; height:100%; opacity: 0.35;" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
                <circle cx="20" cy="80" r="30" fill="#A8D8EA" />
                <circle cx="80" cy="20" r="40" fill="#E8A87C" />
                <circle cx="60" cy="70" r="20" fill="#C3B1E1" />
                <path d="M0,50 Q50,0 100,50 T200,50" stroke="#A8E6CF" stroke-width="0.5" fill="none" />
            </svg>
            <div class="header-content">
                <div class="date-badge">📅 $date_string</div>
                <h1>Günaydın, Fatih.</h1>
                <div style="font-size: 0.9rem; color: #7A7A7A; margin-top:4px;">📍 Doha, Katar</div>
            </div>
        </header>
    </div>

    <!-- Navigation -->
    <nav class="toc-scroller">
        <a href="#odak" class="toc-link">Odak</a>
        <a href="#hava" class="toc-link">Hava</a>
        <a href="#astro" class="toc-link">Astro</a>
        <a href="#karar" class="toc-link">Karar</a>
        <a href="#is" class="toc-link">İş</a>
        <a href="#finans" class="toc-link">Finans</a>
    </nav>
    <div class="toc-progress"><div class="toc-progress-bar" id="tocProgress"></div></div>

    <!-- Mood Band - decorative gradient strip -->
    <div class="mood-band"></div>

    <div class="container">
        <!-- AI GENERATED CONTENT INJECTED HERE -->
        $content_body
        
        <!-- Footer -->
        <div class="footer">
            <p>Okuma süresi: ~2.5 dk</p>
            <p class="data-freshness">Veri tazeliği: Hava $weather_time — Finans $finance_time ($market_status)</p>
            <p style="opacity: 0.5;">© 2026 Morning Brief - Fatih</p>
        </div>
    </div>
    <script>
        const tocLinks = Array.from(document.querySelectorAll(".toc-link"));
        const sections = tocLinks.map(link => document.querySelector(link.getAttribute("href")));
        const progressBar = document.getElementById("tocProgress");

        const setActive = (id) => {
            tocLinks.forEach(link => link.classList.toggle("active", link.getAttribute("href") === ("#" + id)));
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) setActive(entry.target.id);
            });
        }, { rootMargin: "-40% 0px -50% 0px", threshold: 0 });

        sections.forEach(section => section && observer.observe(section));

        const onScroll = () => {
            const doc = document.documentElement;
            const scrollTop = doc.scrollTop || document.body.scrollTop;
            const scrollHeight = doc.scrollHeight - doc.clientHeight;
            const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
            if (progressBar) progressBar.style.width = pct + "%";
        };
        document.addEventListener("scroll", onScroll, { passive: true });
        onScroll();
    </script>
</body>
</html>
""")

def get_current_time_qatar():
    qatar_tz = pytz.timezone(TIMEZONE)
    return datetime.datetime.now(qatar_tz)

def _validate_html_template_placeholders():
    allowed = {
        "gen_time",
        "date_string",
        "content_body",
        "weather_time",
        "finance_time",
        "market_status",
    }
    template_str = HTML_TEMPLATE.template
    # Guard against JS template literals that can hide ${...} placeholders.
    if "`" in template_str:
        raise ValueError("HTML template contains backticks; avoid JS template literals to prevent ${...} collisions.")
    # Find all $ident or ${ident} occurrences.
    import re
    matches = re.findall(r"\$(?:\{)?([A-Za-z_][A-Za-z0-9_]*)\}?", template_str)
    unexpected = sorted({name for name in matches if name not in allowed})
    if unexpected:
        raise ValueError(f"Unexpected template placeholders found: {', '.join(unexpected)}")

def _ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def _load_cache(name, ttl_minutes):
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        ts = datetime.datetime.fromisoformat(payload.get("ts"))
        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - ts).total_seconds() <= ttl_minutes * 60:
            return payload
    except Exception:
        return None
    return None

def _save_cache(name, data):
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, name)
    payload = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "data": data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

def _format_time_for_display(dt_obj, tz_name):
    tz = pytz.timezone(tz_name)
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
    return dt_obj.astimezone(tz).strftime("%d.%m.%Y %H:%M")

def _market_status_us(now_utc):
    eastern = pytz.timezone("US/Eastern")
    now_et = now_utc.astimezone(eastern)
    if now_et.weekday() >= 5:
        return "Piyasa kapalı (hafta sonu)"
    open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if open_time <= now_et <= close_time:
        return "Piyasa açık"
    return "Piyasa kapalı (saat dışı)"

class _HTMLSanitizer(HTMLParser):
    def __init__(self, allowed_tags, allowed_attrs):
        super().__init__(convert_charrefs=True)
        self.allowed_tags = allowed_tags
        self.allowed_attrs = allowed_attrs
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            return
        safe_attrs = []
        for k, v in attrs:
            if k in self.allowed_attrs.get(tag, set()):
                safe_attrs.append((k, v))
        attr_str = "".join([f' {k}="{v}"' for k, v in safe_attrs])
        self.parts.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag in self.allowed_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

def _sanitize_html(raw_html):
    allowed_tags = {
        "div", "p", "ul", "li", "strong", "em", "span", "a", "br",
        "h2", "h3", "h4",
        "svg", "circle", "line", "path", "g", "ellipse", "polygon",
    }
    allowed_attrs = {
        "div": {"class", "id", "style"},
        "p": {"style"},
        "ul": {"class"},
        "li": {"class"},
        "span": {"class", "style"},
        "a": {"href", "target", "style"},
        "h2": {"class"},
        "h3": {"class"},
        "h4": {"class"},
        "svg": {"width", "height", "viewBox", "viewbox", "fill", "xmlns", "style", "preserveAspectRatio", "preserveaspectratio"},
        "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width"},
        "line": {"x1", "x2", "y1", "y2", "stroke", "stroke-width", "stroke-linecap"},
        "path": {"d", "stroke", "stroke-width", "fill"},
        "g": {"stroke", "stroke-width", "stroke-linecap"},
        "ellipse": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width"},
        "polygon": {"points", "fill", "stroke", "stroke-width"},
    }
    parser = _HTMLSanitizer(allowed_tags, allowed_attrs)
    parser.feed(raw_html)
    return "".join(parser.parts)

def _escape_template_like_sequences(text):
    # Prevent accidental `${...}` sequences from surviving into templates or emails.
    return text.replace("${", "&#36;{")

def _ensure_required_sections(raw_html):
    required_ids = ["odak", "hava", "astro", "karar", "is", "finans"]
    missing = [sec for sec in required_ids if f'id="{sec}"' not in raw_html]
    if not missing:
        return raw_html
    fallback_blocks = []
    for sec in missing:
        fallback_blocks.append(
            f'<div class="section-wrapper" id="{sec}"><div class="card"><p>Bu bölüm şu an üretilemedi. Lütfen tekrar deneyin.</p></div></div>'
        )
    return raw_html + "\n" + "\n".join(fallback_blocks)

def format_date_str(now):
    months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return f"{now.day} {months[now.month]} {now.year}, {days[now.weekday()]}"

def send_email(html_content, date_str):
    print("--- 📧 E-POSTA GÖNDERİM SÜRECİ BAŞLADI ---")
    
    # Debug Checks
    if not EMAIL_USER:
        print("❌ HATA: 'EMAIL_USER' secret tanımlı değil!")
        return
    if not EMAIL_PASS:
        print("❌ HATA: 'EMAIL_PASS' secret tanımlı değil!")
        return
    if not EMAIL_TO:
        print("❌ HATA: 'EMAIL_TO' secret tanımlı değil!")
        return

    print(f"✅ Kimlik bilgileri bulundu. Gönderen: {EMAIL_USER} -> Alıcı: {EMAIL_TO}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Morning Brief: {date_str}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    # We send the rich HTML
    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        print("🔌 Gmail SMTP sunucusuna (smtp.gmail.com:465) bağlanılıyor...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        
        print("🔐 Giriş yapılıyor...")
        server.login(EMAIL_USER, EMAIL_PASS)
        
        print("📨 Mesaj gönderiliyor...")
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        
        server.quit()
        print("✅ BAŞARILI: E-posta başarıyla gönderildi!")
    except smtplib.SMTPAuthenticationError:
        print("❌ HATA: Kullanıcı adı veya şifre yanlış! (App Password kullandığından emin misin?)")
    except Exception as e:
        print(f"❌ BEKLENMEYEN HATA: {str(e)}")

def _weather_icon_class(code):
    """Map WMO weather code to icon class: sunny, partly-cloudy, cloudy, rainy, stormy."""
    if code in (0, 1):
        return "sunny"
    elif code in (2, 3):
        return "cloudy"
    elif code in (45, 48):
        return "cloudy"
    elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "rainy"
    elif code in (71, 73, 75):
        return "cloudy"
    elif code in (95, 96, 99):
        return "stormy"
    return "partly-cloudy"


# Inline SVG weather icons (pastel, cartoony)
WEATHER_SVGS = {
    "sunny": '<svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="26" cy="26" r="12" fill="#F6D87E" stroke="#E8A87C" stroke-width="2"/><g stroke="#E8A87C" stroke-width="2" stroke-linecap="round"><line x1="26" y1="4" x2="26" y2="10"/><line x1="26" y1="42" x2="26" y2="48"/><line x1="4" y1="26" x2="10" y2="26"/><line x1="42" y1="26" x2="48" y2="26"/><line x1="10.4" y1="10.4" x2="14.6" y2="14.6"/><line x1="37.4" y1="37.4" x2="41.6" y2="41.6"/><line x1="10.4" y1="41.6" x2="14.6" y2="37.4"/><line x1="37.4" y1="14.6" x2="41.6" y2="10.4"/></g></svg>',
    "partly-cloudy": '<svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="18" r="9" fill="#F6D87E" stroke="#E8A87C" stroke-width="1.5"/><g stroke="#E8A87C" stroke-width="1.5" stroke-linecap="round"><line x1="20" y1="4" x2="20" y2="7"/><line x1="9" y1="7" x2="11" y2="9.5"/><line x1="5" y1="18" x2="8" y2="18"/><line x1="31" y1="7" x2="29" y2="9.5"/></g><ellipse cx="30" cy="34" rx="14" ry="9" fill="#D8EAF6" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="22" cy="31" r="7" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="36" cy="31" r="6" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/></svg>',
    "cloudy": '<svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="28" cy="32" rx="16" ry="10" fill="#D8EAF6" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="18" cy="28" r="9" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="34" cy="27" r="7" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="26" cy="22" r="6" fill="#EEF4FB" stroke="#A8D8EA" stroke-width="1.5"/></svg>',
    "rainy": '<svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="26" cy="22" rx="15" ry="10" fill="#D8EAF6" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="16" cy="18" r="8" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/><circle cx="33" cy="18" r="7" fill="#E4F0FA" stroke="#A8D8EA" stroke-width="1.5"/><g stroke="#A8D8EA" stroke-width="1.8" stroke-linecap="round"><line x1="16" y1="34" x2="14" y2="40"/><line x1="24" y1="34" x2="22" y2="42"/><line x1="32" y1="34" x2="30" y2="40"/></g></svg>',
    "stormy": '<svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="26" cy="20" rx="15" ry="10" fill="#C8C8D8" stroke="#9A9AB0" stroke-width="1.5"/><circle cx="16" cy="16" r="8" fill="#D4D4E0" stroke="#9A9AB0" stroke-width="1.5"/><circle cx="33" cy="16" r="7" fill="#D4D4E0" stroke="#9A9AB0" stroke-width="1.5"/><polygon points="24,30 28,30 25,38 30,38 22,48 25,40 21,40" fill="#F6D87E" stroke="#E8A87C" stroke-width="1"/><g stroke="#A8D8EA" stroke-width="1.8" stroke-linecap="round"><line x1="14" y1="34" x2="12" y2="40"/><line x1="36" y1="34" x2="34" y2="40"/></g></svg>',
}


def get_weather_data():
    """Fetch hourly weather forecast for Doha using Open-Meteo API (no API key needed)."""
    try:
        cached = _load_cache("weather.json", ttl_minutes=60)
        if cached:
            return cached["data"]["text"], cached["data"]["icon"], cached["data"]["fetched_at"]

        # WMO weather code descriptions in Turkish
        wmo_codes = {
            0: "Açık", 1: "Az bulutlu", 2: "Parçalı bulutlu", 3: "Bulutlu",
            45: "Sisli", 48: "Kırağılı sis",
            51: "Hafif çisenti", 53: "Çisenti", 55: "Yoğun çisenti",
            61: "Hafif yağmur", 63: "Yağmur", 65: "Şiddetli yağmur",
            71: "Hafif kar", 73: "Kar", 75: "Yoğun kar",
            80: "Hafif sağanak", 81: "Sağanak", 82: "Şiddetli sağanak",
            95: "Gök gürültülü fırtına", 96: "Dolu ile fırtına", 99: "Şiddetli dolu fırtınası",
        }

        params = urllib.parse.urlencode({
            "latitude": DOHA_LAT,
            "longitude": DOHA_LNG,
            "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "Asia/Qatar",
            "forecast_days": 1,
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "MorningBrief/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        feels = hourly.get("apparent_temperature", [])
        humidity = hourly.get("relative_humidity_2m", [])
        codes = hourly.get("weather_code", [])
        wind = hourly.get("wind_speed_10m", [])

        if not times:
            return "(Hava durumu verisi alınamadı.)", "partly-cloudy", datetime.datetime.now(datetime.timezone.utc).isoformat()

        lines = []
        for i in range(len(times)):
            hour = times[i].split("T")[1][:5]
            desc = wmo_codes.get(codes[i], f"Kod:{codes[i]}")
            lines.append(
                f"  {hour} | {temps[i]:.0f}°C (hissedilen {feels[i]:.0f}°C) | {desc} | "
                f"Nem %{humidity[i]:.0f} | Rüzgar {wind[i]:.0f} km/s"
            )

        # Determine dominant weather condition (daytime hours 6-20)
        daytime_codes = [codes[i] for i in range(len(times)) if 6 <= int(times[i].split("T")[1][:2]) <= 20]
        if daytime_codes:
            from collections import Counter
            most_common_code = Counter(daytime_codes).most_common(1)[0][0]
            dominant = _weather_icon_class(most_common_code)
        else:
            dominant = _weather_icon_class(codes[0])

        # Summary stats
        temp_max = max(temps)
        temp_min = min(temps)
        summary = f"  Gün özeti: Min {temp_min:.0f}°C / Max {temp_max:.0f}°C"

        weather_text = f"""DOHA HAVA DURUMU (Open-Meteo - Saatlik Tahmin):
{summary}

Saatlik detay:
""" + "\n".join(lines)

        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _save_cache("weather.json", {"text": weather_text, "icon": dominant, "fetched_at": fetched_at})
        return weather_text, dominant, fetched_at

    except Exception as e:
        print(f"⚠️ Hava durumu hatası: {e}")
        return "(Hava durumu verisi alınamadı.)", "partly-cloudy", datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_financial_data():
    """Fetch real market data for whitelisted tickers via Yahoo Finance."""
    WHITELIST = ["QQQI", "FDVV", "SCHD", "SCHG", "IAUI", "SLV"]
    try:
        cached = _load_cache("finance.json", ttl_minutes=30)
        if cached:
            return cached["data"]["text"], cached["data"]["fetched_at"], cached["data"]["latest_ts"]

        lines = []
        latest_ts = None
        data = yf.download(WHITELIST, period="5d", group_by="ticker", auto_adjust=False, progress=False)
        for symbol in WHITELIST:
            try:
                if hasattr(data.columns, "levels"):
                    hist = data[symbol] if symbol in data.columns.levels[0] else None
                else:
                    hist = data[symbol] if symbol in data else None
                if hist is None or hist.empty:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="5d")
                if hist.empty:
                    lines.append(f"  {symbol}: Veri alınamadı")
                    continue

                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                change_pct = ((current - prev) / prev) * 100

                if hist.index is not None and len(hist.index) > 0:
                    ts = hist.index[-1]
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts

                if len(hist) >= 5:
                    week_start = hist["Close"].iloc[0]
                    week_change = ((current - week_start) / week_start) * 100
                    week_str = f" | 5g: {week_change:+.2f}%"
                else:
                    week_str = ""

                direction = "yukari" if change_pct >= 0 else "asagi"
                lines.append(
                    f"  {symbol}: ${current:.2f} ({change_pct:+.2f}% {direction}){week_str} | Hacim: {hist['Volume'].iloc[-1]:,.0f}"
                )
            except Exception as e:
                lines.append(f"  {symbol}: Hata - {str(e)[:50]}")

        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        latest_ts_str = latest_ts.isoformat() if latest_ts is not None else fetched_at
        text = "GERÇEK PİYASA VERİLERİ (Yahoo Finance):\n" + "\n".join(lines)
        _save_cache("finance.json", {"text": text, "fetched_at": fetched_at, "latest_ts": latest_ts_str})
        return text, fetched_at, latest_ts_str
    except Exception as e:
        print(f"⚠️ Finansal veri hatası: {e}")
        return "(Finansal veri alınamadı, genel bilgi kullan.)", datetime.datetime.now(datetime.timezone.utc).isoformat(), datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_planetary_data(now_qatar):
    """Compute real planetary positions using Swiss Ephemeris via kerykeion."""
    try:
        # Current sky (transit chart) from Doha
        transit = AstrologicalSubjectFactory.from_birth_data(
            name="Güncel Gökyüzü",
            year=now_qatar.year,
            month=now_qatar.month,
            day=now_qatar.day,
            hour=now_qatar.hour,
            minute=now_qatar.minute,
            lng=DOHA_LNG,
            lat=DOHA_LAT,
            tz_str=DOHA_TZ,
            online=False,
        )

        # Fatih's natal chart
        natal = AstrologicalSubjectFactory.from_birth_data(
            name="Fatih",
            year=NATAL_YEAR,
            month=NATAL_MONTH,
            day=NATAL_DAY,
            hour=NATAL_HOUR,
            minute=NATAL_MINUTE,
            lng=NATAL_LNG,
            lat=NATAL_LAT,
            tz_str=NATAL_TZ,
            online=False,
        )

        # Zodiac sign Turkish mapping
        sign_tr = {
            "Ari": "Koç", "Tau": "Boğa", "Gem": "İkizler", "Can": "Yengeç",
            "Leo": "Aslan", "Vir": "Başak", "Lib": "Terazi", "Sco": "Akrep",
            "Sag": "Yay", "Cap": "Oğlak", "Aqu": "Kova", "Pis": "Balık",
        }

        planets = [
            ("Güneş", transit.sun), ("Ay", transit.moon),
            ("Merkür", transit.mercury), ("Venüs", transit.venus),
            ("Mars", transit.mars), ("Jüpiter", transit.jupiter),
            ("Satürn", transit.saturn), ("Uranüs", transit.uranus),
            ("Neptün", transit.neptune), ("Plüton", transit.pluto),
        ]

        natal_planets = [
            ("Güneş", natal.sun), ("Ay", natal.moon),
            ("Merkür", natal.mercury), ("Venüs", natal.venus),
            ("Mars", natal.mars), ("Jüpiter", natal.jupiter),
            ("Satürn", natal.saturn),
        ]

        # Build transit positions text
        lines = []
        for name, planet in planets:
            sign = sign_tr.get(planet.sign, planet.sign)
            retro = " (Retrograd)" if getattr(planet, 'retrograde', False) else ""
            lines.append(f"  {name}: {sign} {planet.position:.1f}°{retro}")

        transit_text = "\n".join(lines)

        # Build natal positions text
        natal_lines = []
        for name, planet in natal_planets:
            sign = sign_tr.get(planet.sign, planet.sign)
            natal_lines.append(f"  {name}: {sign} {planet.position:.1f}°")

        natal_text = "\n".join(natal_lines)

        # Moon phase info
        moon_sign = sign_tr.get(transit.moon.sign, transit.moon.sign)
        moon_deg = transit.moon.position

        return f"""
GERÇEK GEZEGENSEl VERİLER (Swiss Ephemeris - bugünkü hesaplama):

GÜNCEL TRANSİT POZİSYONLARI (Doha, {now_qatar.strftime('%d.%m.%Y %H:%M')}):
{transit_text}

FATİH'İN NATAL HARİTASI (14.06.1989, 09:45, İstanbul):
{natal_lines[0]}
  Güneş: İkizler, Ay: Terazi, Yükselen: Aslan
{natal_text}

AY BİLGİSİ:
  Ay şu anda {moon_sign} burcunda, {moon_deg:.1f}° konumunda.
"""
    except Exception as e:
        print(f"⚠️ Ephemeris hesaplama hatası: {e}")
        return "\n(Ephemeris verisi hesaplanamadı, genel astroloji bilgisi kullan.)\n"


def generate_daily_brief():
    if not API_KEY:
        print("Error: GEMINI_API_KEY not found.")
        return

    _validate_html_template_placeholders()

    client = genai.Client(api_key=API_KEY)
    
    # Time Calc
    now_qatar = get_current_time_qatar()
    date_str = format_date_str(now_qatar)
    gen_time_str = now_qatar.strftime("%H:%M:%S")

    print(f"Generating brief for: {date_str}...")

    # Compute real planetary positions
    planetary_data = get_planetary_data(now_qatar)

    # Fetch real financial data
    financial_data, finance_fetched_at, finance_latest_ts = get_financial_data()

    # Fetch weather forecast
    weather_data, weather_icon_key, weather_fetched_at = get_weather_data()
    weather_icon_svg = WEATHER_SVGS.get(weather_icon_key, WEATHER_SVGS["partly-cloudy"])

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    market_status = _market_status_us(now_utc)
    weather_time_display = _format_time_for_display(datetime.datetime.fromisoformat(weather_fetched_at), TIMEZONE)
    finance_time_display = _format_time_for_display(datetime.datetime.fromisoformat(finance_latest_ts), "US/Eastern")

    # --- ENRICHED PROMPT WITH REAL EPHEMERIS DATA ---
    prompt = f"""
    Sen Fatih için "Morning Brief" hazırlayan, çok zeki ve biraz da esprili bir astroloji & finans asistanısın.

    PARAMETRELER:
    - Tarih: {date_str} (Zaman dilimi: Asia/Qatar).
    - Kullanıcı: Fatih (Doğum: {USER_BIRTH_DATA}).
    - Astro Kimlik: Güneş İkizler, Ay Terazi, Yükselen Aslan.
    - Dil: Türkçe.
    - Ton: Kısa, net, bullet-point ağırlıklı. Mobil öncelikli.

    {planetary_data}

    PORTFÖY İZLEME LISTESI (Whitelist): QQQI, FDVV, SCHD, SCHG, IAUI, SLV.
    YASAKLI LISTE (Blacklist): YMAG, TQQQ, GLDW.

    {financial_data}

    {weather_data}

    TAKİP EDİLEN ASTROLOG KAYNAKLARI:
    {ASTROLOGER_SOURCES}

    {ASTROLOGY_BOOKS}

    GÖREV:
    Aşağıdaki HTML yapısına BİREBİR uyarak sadece BODY içeriğini (header/footer hariç) üret.
    Her bölümü <div class="section-wrapper" id="...">...</div> içine al.

    İSTENEN BÖLÜMLER VE HTML YAPISI:

    1. ODAK ÇAPASI (ID: odak):
       - <div class="card" style="border-left: 4px solid var(--accent-primary);"> kullan.
       - İçinde bir Motto ve "3 Kelime Kuralı" olsun.
       - Hemen altına kısa (1-2 cümle) bir ruh hali geçiş analizi yap (dün→bugün mood).

    2. HAVA DURUMU (ID: hava):
       - MUTLAKA şu yapıyı kullan:
         <div class="weather-card">
           <div class="weather-icon-wrap">
             {weather_icon_svg}
             <div class="weather-summary">... özet ...</div>
           </div>
           <div class="weather-periods">
             <div class="weather-period"><strong>Sabah</strong>...</div>
             <div class="weather-period"><strong>Öğle</strong>...</div>
             <div class="weather-period"><strong>Akşam</strong>...</div>
           </div>
           <p style="margin-top:8px; font-size:0.8rem; color:#7A7A7A;">Veri zamanı: {weather_time_display}</p>
           <p style="margin-top:8px;"><em>Ne giymeliyim: ...</em></p>
         </div>
       - YUKARIDA VERİLEN GERÇEK HAVA DURUMU VERİLERİNİ KULLAN.
       - Sabah (06-09), öğle (12-15), akşam (18-21) sıcaklık aralığı ve durumu yaz.
       - "Ne giymeliyim?" pratik önerisi ekle.
       - <span class="tag tag-blue"> ile hava durumu etiketleri kullanabilirsin.

    3. HOROSKOP (ID: astro):
       - YUKARIDA VERİLEN GERÇEK GEZEGENSEl VERİLERİ KULLAN. Uydurma yapma!
       - Güncel transit pozisyonlarını Fatih'in natal haritasıyla karşılaştır.
       - Aslan Yükselen ve Kova/İkizler transitlerine odaklan.
       - Gezegen retroları varsa mutlaka belirt.
       - <span class="tag tag-blue"> gibi renkli etiketler kullan (tag-blue, tag-gold, tag-red, tag-green, tag-lavender).
       - "Astro-Bilişsel Uyarı" başlığı altında bir <div class="card" style="background: #EDE7F6;"> ekle.
       - Bölümün sonuna "Günün Astroloji Kaynakları" başlığı altında yukarıdaki astrolog listesinden 2-3 astrolog seç ve
         şu formatta link ver: <a href="URL" target="_blank" style="color: #8B72B2; text-decoration: none;">İsim</a>.
         Farklı günlerde farklı astrologları öner, her gün aynılarını koyma.
         Ayrıca referans kitaplarından birini de "Okuma Önerisi" olarak ekle.

    4. KARAR ZAMAN HARİTASI (ID: karar):
       - Gerçek transit verilerine göre karar zamanlarını belirle.
       - MUTLAKA şu grid yapısını kullan:
         <div class="decision-grid">
            <div class="decision-box">...Simge, EN İYİ, Eylem...</div>
            <div class="decision-box">...Simge, NÖTR, Eylem...</div>
            <div class="decision-box">...Simge, KAÇIN, Eylem...</div>
         </div>

    5. İŞ & KARİYER (ID: is):
       - Bullet list kullan (<ul class="bullet-list">).
       - Yükselen Aslan liderliği ile İkizler zekasını birleştir.
       - Günün transit verilerini iş kararlarına yansıt.

    6. FİNANS (ID: finans):
       - YUKARIDA VERİLEN GERÇEK PİYASA VERİLERİNİ KULLAN. Fiyat ve değişim yüzdelerini göster.
       - Fatih'in Whitelist'indeki hisseler için somut "Davranışsal Notlar" yaz.
       - Her hissenin gerçek fiyatını ve günlük değişimini belirt.
       - Hisse adlarını <span class="ticker-pill">HİSSE</span> şeklinde yaz.
       - Uydurma fiyat verme, yukarıdaki Yahoo Finance verilerini kullan.
       - Bölümün hemen başında küçük bir satır ekle: "Veri zamanı: {finance_time_display} (US/Eastern) — {market_status}"

    7. TEK SORU:
       - Günün düşündürücü sorusu (astrolojik temalarla bağlantılı olabilir).

    ÖNEMLİ KURALLAR:
    - Asla ```html``` bloğu koyma, sadece saf HTML kodu döndür.
    - Asla <html>, <head>, <body> taglerini açma.
    - <div class="visual-mood"> KULLANMA. Mood band zaten template'te var.
    - Light mode (krem/pastel tonlar) uyumlu ol. Arka plan açık renk, yazılar koyu. CSS class'ları doğru kullan.
    - Renkli etiketler için tag-blue, tag-gold, tag-red, tag-green, tag-lavender class'larını kullan.
    - Horoskop bölümünde gerçek gezegen pozisyonlarını kullan, uydurma bilgi verme.
    - Astroloji kaynaklarına link verirken sadece yukarıda listelenen güvenilir kaynakları kullan.
    - Bölümler arası gereksiz boşluk bırakma, kompakt tut.
    - Tüm metin boyutları tutarlı olsun (0.95rem), başlıklar hariç.
    """

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    
    # Temizlik
    raw_html = response.text.replace("```html", "").replace("```", "").strip()
    raw_html = _sanitize_html(raw_html)
    raw_html = _escape_template_like_sequences(raw_html)
    raw_html = _ensure_required_sections(raw_html)
    
    # Template Birleştirme
    final_html = HTML_TEMPLATE.substitute(
        date_string=date_str,
        content_body=raw_html,
        gen_time=gen_time_str,
        weather_time=weather_time_display,
        finance_time=finance_time_display,
        market_status=market_status
    )

    # 1. Dosyaya Yaz (Web İçin)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    # 2. Email Gönder
    send_email(final_html, date_str)

if __name__ == "__main__":
    generate_daily_brief()
