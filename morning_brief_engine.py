import os
import datetime
import pytz
import smtplib
import json
import urllib.request
import urllib.parse
import re
import html
from html.parser import HTMLParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from string import Template
from kerykeion import AstrologicalSubjectFactory
import yfinance as yf

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
EMAIL_RENDER_MODE = os.environ.get("EMAIL_RENDER_MODE") or "email-safe"
THEME_PROFILE = os.environ.get("THEME_PROFILE") or "offwhite-slate"
EMAIL_HTML_BUDGET_BYTES = int(os.environ.get("EMAIL_HTML_BUDGET_BYTES") or "102400")
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
- Willow Grace Astrology: YouTube https://www.youtube.com/@willowgraceastrology
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

# --- THE HTML TEMPLATE (EMAIL-SAFE, TABLE-FIRST) ---
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Brief | Fatih</title>
    <style>
      body, table, td, p, a, span, div {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      }
      img {
        display: block;
        border: 0;
        outline: none;
        text-decoration: none;
      }
      p {
        margin: 0 0 12px 0;
      }
      .section-wrapper {
        padding: 0 0 12px 0;
      }
      .card {
        background-color: #FFFFFF;
        border: 1px solid #D0D3DC;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
      }
      .card-title {
        font-size: 16px;
        font-weight: 700;
        color: #1F2933;
        line-height: 1.4;
      }
      .tag {
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        padding: 3px 8px;
        border-radius: 8px;
        letter-spacing: 0.3px;
      }
      .tag-blue { background-color: #EAF3FA; color: #2B7CAB; border: 1px solid #CDE4F4; }
      .tag-gold { background-color: #FDEDE5; color: #C85826; border: 1px solid #F7CBB5; }
      .tag-red { background-color: #FDEDE5; color: #C85826; border: 1px solid #F7CBB5; }
      .tag-green { background-color: #E9F8F0; color: #1D8F56; border: 1px solid #BEE8D0; }
      .tag-lavender { background-color: #EEF4F8; color: #4B5563; border: 1px solid #D0D3DC; }
      .weather-card {
        background-color: #F6F6F7;
        border: 1px solid #D0D3DC;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 12px;
      }
      .weather-summary {
        font-size: 15px;
        color: #1F2933;
        line-height: 1.5;
      }
      .weather-period {
        background-color: #FFFFFF;
        border: 1px solid #D0D3DC;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
        font-size: 14px;
        color: #1F2933;
        line-height: 1.45;
      }
      .decision-box {
        background-color: #FFFFFF;
        border: 1px solid #D0D3DC;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
      }
      .d-good { color: #26B46D; }
      .d-bad { color: #EE763A; }
      .d-neutral { color: #4B5563; }
      .ticker-pill {
        display: inline-block;
        background-color: #FDEDE5;
        border: 1px solid #F7CBB5;
        border-radius: 4px;
        padding: 2px 8px;
        color: #C85826;
        font-family: "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
        font-size: 13px;
      }
      .bullet-list {
        margin: 0;
        padding-left: 18px;
      }
      .bullet-list li {
        margin: 0 0 8px 0;
        color: #1F2933;
      }
      .finance-list {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .finance-list li {
        background-color: #FFFFFF;
        border: 1px solid #D0D3DC;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
      }
      .source-link {
        color: #2B7CAB;
        text-decoration: underline;
      }
    </style>
</head>
<body style="margin:0; padding:0; background-color:#F6F6F7; color:#1F2933;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      Morning Brief: Astroloji, hava ve finans ozeti.
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#F6F6F7;">
      <tr>
        <td align="center" style="padding:0 12px 24px 12px;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:680px; width:100%;">
            <tr>
              <td style="padding:6px 14px; background-color:#D0D3DC; color:#4B5563; font-size:11px; text-align:right;">
                SON GUNCELLEME: $gen_time (Qatar)
              </td>
            </tr>
            <tr>
              <td style="padding:18px; background-color:#FFFFFF; border:1px solid #D0D3DC; border-top:none;">
                <p style="display:inline-block; margin:0 0 8px 0; font-size:12px; color:#C85826; background-color:#FDEDE5; border:1px solid #F7CBB5; border-radius:8px; padding:4px 8px;">
                  📅 $date_string
                </p>
                <p style="margin:0; font-size:30px; line-height:1.15; font-weight:800; color:#1F2933;">Gunaydin, Fatih.</p>
                <p style="margin:6px 0 0 0; font-size:13px; color:#4B5563;">📍 Doha, Katar</p>
              </td>
            </tr>
            <tr>
              <td style="padding:10px 18px 8px 18px;">
                <p style="margin:0; font-size:12px; color:#4B5563; line-height:1.5;">
                  <a href="#odak" style="color:#2B7CAB; text-decoration:none;">Odak</a> ·
                  <a href="#hava" style="color:#2B7CAB; text-decoration:none;">Hava</a> ·
                  <a href="#astro" style="color:#2B7CAB; text-decoration:none;">Astro</a> ·
                  <a href="#karar" style="color:#2B7CAB; text-decoration:none;">Karar</a> ·
                  <a href="#is" style="color:#2B7CAB; text-decoration:none;">Is</a> ·
                  <a href="#finans" style="color:#2B7CAB; text-decoration:none;">Finans</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 18px 14px 18px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="height:4px; background-color:#6EB6E8;" width="33%"></td>
                    <td style="height:4px; background-color:#26B46D;" width="34%"></td>
                    <td style="height:4px; background-color:#EE763A;" width="33%"></td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:0 18px;">
                $content_body
              </td>
            </tr>
            <tr>
              <td style="padding:16px 18px 24px 18px; text-align:center; border-top:1px solid #D0D3DC;">
                <p style="margin:0; font-size:12px; color:#4B5563;">Okuma suresi: ~2.5 dk</p>
                <p style="margin:6px 0 0 0; font-size:12px; color:#4B5563;">Veri tazeligi: Hava $weather_time — Finans $finance_time ($market_status)</p>
                <p style="margin:8px 0 0 0; font-size:11px; color:#6B7280;">© 2026 Morning Brief - Fatih</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
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
        safe_attrs = {}
        for k, v in attrs:
            if k in self.allowed_attrs.get(tag, set()):
                safe_attrs[k] = v

        class_name = safe_attrs.get("class", "")
        class_style = _style_for_classes(class_name)
        if class_style:
            existing = safe_attrs.get("style", "")
            safe_attrs["style"] = _merge_styles(existing, class_style)

        attr_str = "".join([f' {k}="{v}"' for k, v in safe_attrs.items()])
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


EMAIL_CLASS_STYLES = {
    "section-wrapper": "padding:0 0 12px 0;",
    "card": "background-color:#FFFFFF;border:1px solid #D0D3DC;border-radius:12px;padding:16px;margin-bottom:10px;",
    "card-header": "margin-bottom:8px;",
    "card-title": "font-size:16px;font-weight:700;color:#1F2933;line-height:1.4;",
    "tag": "display:inline-block;font-size:11px;font-weight:700;text-transform:uppercase;padding:3px 8px;border-radius:8px;letter-spacing:0.3px;",
    "tag-blue": "background-color:#EAF3FA;color:#2B7CAB;border:1px solid #CDE4F4;",
    "tag-gold": "background-color:#FDEDE5;color:#C85826;border:1px solid #F7CBB5;",
    "tag-red": "background-color:#FDEDE5;color:#C85826;border:1px solid #F7CBB5;",
    "tag-green": "background-color:#E9F8F0;color:#1D8F56;border:1px solid #BEE8D0;",
    "tag-lavender": "background-color:#EEF4F8;color:#4B5563;border:1px solid #D0D3DC;",
    "weather-card": "background-color:#F6F6F7;border:1px solid #D0D3DC;border-radius:12px;padding:14px;margin-bottom:12px;",
    "weather-icon-wrap": "margin-bottom:10px;",
    "weather-summary": "font-size:15px;color:#1F2933;line-height:1.5;",
    "weather-periods": "margin-top:8px;",
    "weather-period": "background-color:#FFFFFF;border:1px solid #D0D3DC;border-radius:10px;padding:10px;margin-bottom:8px;font-size:14px;color:#1F2933;line-height:1.45;",
    "decision-grid": "margin-top:8px;",
    "decision-box": "background-color:#FFFFFF;border:1px solid #D0D3DC;border-radius:10px;padding:10px;margin-bottom:8px;",
    "d-icon": "font-size:16px;margin-right:6px;",
    "d-label": "font-size:12px;color:#4B5563;font-weight:600;",
    "d-val": "font-size:14px;font-weight:700;color:#1F2933;",
    "d-good": "color:#26B46D;",
    "d-bad": "color:#EE763A;",
    "d-neutral": "color:#4B5563;",
    "ticker-pill": "display:inline-block;background-color:#FDEDE5;border:1px solid #F7CBB5;border-radius:4px;padding:2px 8px;color:#C85826;font-family:\"SFMono-Regular\",Menlo,Consolas,\"Liberation Mono\",monospace;font-size:13px;",
    "bullet-list": "margin:0;padding-left:18px;",
    "finance-list": "list-style:none;padding:0;margin:0;",
    "source-link": "color:#2B7CAB;text-decoration:underline;",
}


def _merge_styles(existing_style, extra_style):
    existing = (existing_style or "").strip().rstrip(";")
    extra = (extra_style or "").strip().rstrip(";")
    if existing and extra:
        return f"{existing};{extra};"
    if existing:
        return f"{existing};"
    if extra:
        return f"{extra};"
    return ""


def _style_for_classes(class_name):
    if not class_name:
        return ""
    styles = []
    for cls in class_name.split():
        style = EMAIL_CLASS_STYLES.get(cls)
        if style:
            styles.append(style)
    return "".join(styles)

def _sanitize_html(raw_html):
    allowed_tags = {
        "div", "p", "ul", "li", "strong", "em", "span", "a", "br", "img",
        "table", "tbody", "tr", "td",
        "h2", "h3", "h4",
    }
    allowed_attrs = {
        "div": {"class", "id", "style"},
        "p": {"style"},
        "ul": {"class"},
        "li": {"class"},
        "span": {"class", "style"},
        "a": {"href", "target", "style", "class"},
        "img": {"src", "alt", "width", "height", "style"},
        "table": {"class", "style", "width", "cellpadding", "cellspacing", "border", "role"},
        "tbody": {"class", "style"},
        "tr": {"class", "style"},
        "td": {"class", "style", "width", "colspan", "rowspan", "align", "valign"},
        "h2": {"class"},
        "h3": {"class"},
        "h4": {"class"},
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


def _html_to_plain_text(html_content):
    text = re.sub(r"(?i)<br\s*/?>", "\n", html_content)
    text = re.sub(r"(?i)</(p|div|tr|td|li|h1|h2|h3|h4)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"(?i)<[^>]+>", "", text)
    text = html.unescape(text)
    lines = []
    prev_blank = False
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if not prev_blank:
                lines.append("")
            prev_blank = True
            continue
        lines.append(line)
        prev_blank = False
    return "\n".join(lines).strip()


def _log_payload_size(html_content):
    payload = len(html_content.encode("utf-8"))
    print(f"📦 HTML payload size: {payload} bytes")
    if payload > EMAIL_HTML_BUDGET_BYTES:
        print(
            f"⚠️ HTML payload exceeds budget ({EMAIL_HTML_BUDGET_BYTES} bytes). "
            "Some clients may clip long emails."
        )

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

    plain_text = _html_to_plain_text(html_content)
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

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


WEATHER_ICON_IMAGES = {
    "sunny": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2600.png", "Gunesli"),
    "partly-cloudy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26c5.png", "Parcali bulutlu"),
    "cloudy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2601.png", "Bulutlu"),
    "rainy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f327.png", "Yagmurlu"),
    "stormy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26c8.png", "Firtinali"),
}


def _weather_icon_image_html(icon_key):
    src, alt = WEATHER_ICON_IMAGES.get(icon_key, WEATHER_ICON_IMAGES["partly-cloudy"])
    return (
        f'<img src="{src}" alt="{alt}" width="40" height="40" '
        'style="display:block;width:40px;height:40px;border:0;outline:none;margin:0 0 8px 0;" />'
    )


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
        print("Error: GEMINI_API_KEY (or GOOGLE_API_KEY) not found.")
        return

    _validate_html_template_placeholders()

    client = genai.Client(api_key=API_KEY)
    print(f"Using Gemini model: {GEMINI_MODEL}")
    
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
    weather_icon_html = _weather_icon_image_html(weather_icon_key)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    market_status = _market_status_us(now_utc)
    weather_time_display = _format_time_for_display(datetime.datetime.fromisoformat(weather_fetched_at), TIMEZONE)
    finance_time_display = _format_time_for_display(datetime.datetime.fromisoformat(finance_latest_ts), "US/Eastern")

    if EMAIL_RENDER_MODE != "email-safe":
        print(f"⚠️ Unsupported EMAIL_RENDER_MODE='{EMAIL_RENDER_MODE}'. Falling back to email-safe.")
    if THEME_PROFILE != "offwhite-slate":
        print(f"⚠️ Unsupported THEME_PROFILE='{THEME_PROFILE}'. Falling back to offwhite-slate.")
    print(f"Email render mode: {EMAIL_RENDER_MODE} | Theme: {THEME_PROFILE}")

    # --- ENRICHED PROMPT WITH REAL EPHEMERIS DATA ---
    prompt = f"""
    Sen Fatih için "Morning Brief" hazırlayan, zeki ama net bir astroloji ve finans asistanısın.

    PARAMETRELER:
    - Tarih: {date_str}
    - Kullanıcı: Fatih (Doğum: {USER_BIRTH_DATA})
    - Dil: Türkçe
    - Ton: Kısa, net, mobilde hızlı okunur.

    EMAIL TASARIM KISITLARI (ÇOK ÖNEMLİ):
    - İçerik yalnızca BODY içeriği olsun.
    - Her bölüm: <div class="section-wrapper" id="...">...</div>
    - Sadece bu class adlarını kullan: section-wrapper, card, tag, tag-blue, tag-gold, tag-red, tag-green, tag-lavender,
      weather-card, weather-icon-wrap, weather-summary, weather-periods, weather-period,
      decision-grid, decision-box, d-icon, d-label, d-val, d-good, d-bad, d-neutral,
      bullet-list, finance-list, ticker-pill, source-link.
    - No script, no svg, no canvas, no iframe, no form, no style tag.
    - CSS custom property kullanma.
    - Flex veya grid layout kullanma.
    - Tek kolon, email-uyumlu sade bloklar kullan.
    - Karmaşık animasyon, sticky, hover davranışı istemiyoruz.

    GERÇEK VERİLER:
    {planetary_data}
    {financial_data}
    {weather_data}

    PORTFÖY:
    - Whitelist: QQQI, FDVV, SCHD, SCHG, IAUI, SLV
    - Blacklist: YMAG, TQQQ, GLDW

    ASTROLOJİ KAYNAKLARI:
    {ASTROLOGER_SOURCES}
    {ASTROLOGY_BOOKS}

    BÖLÜMLER:
    1) ODAK (id=odak):
       - Bir motto, 3 kelime kuralı, kısa mood geçiş analizi.
       - card içinde olsun.

    2) HAVA (id=hava):
       - Şu yapıyı kullan:
         <div class="weather-card">
           <div class="weather-icon-wrap">
             {weather_icon_html}
             <div class="weather-summary">...</div>
           </div>
           <div class="weather-periods">
             <div class="weather-period"><strong>Sabah</strong>...</div>
             <div class="weather-period"><strong>Öğle</strong>...</div>
             <div class="weather-period"><strong>Akşam</strong>...</div>
           </div>
           <p style="margin-top:8px; font-size:12px; color:#4B5563;">Veri zamanı: {weather_time_display}</p>
           <p style="margin-top:8px;"><em>Ne giymeliyim: ...</em></p>
         </div>
       - Gerçek hava verisini kullan.

    3) HOROSKOP (id=astro):
       - Gerçek transit + natal sentez.
       - 3-4 paragraf + 3 maddelik kısa liste.
       - Etiketler: tag-blue/tag-gold/tag-red/tag-green/tag-lavender.
       - Kaynak bölümü ekle; en az 5 link (3 Türk + 2 uluslararası), class=source-link.
       - Bir "Astro-Bilişsel Uyarı" card'ı ekle (açık mavi-slate tonunda).

    4) KARAR (id=karar):
       - En iyi, nötr, kaçın alanları.
       - decision-grid içinde 3 adet decision-box; hepsi dikey okunabilir olsun.

    5) İŞ (id=is):
       - <ul class="bullet-list"> ile kısa maddeler.

    6) FİNANS (id=finans):
       - Gerçek fiyat + değişim yüzdesi.
       - Her hisse için davranışsal not.
       - Hisse adını <span class="ticker-pill"> ile yaz.
       - Başta veri zamanı satırı:
         "Veri zamanı: {finance_time_display} (US/Eastern) — {market_status}"
       - Liste yapısı: <ul class="finance-list"><li>...</li></ul>

    7) TEK SORU:
       - Günün düşündürücü sorusu.

    KURALLAR:
    - Yalnızca saf HTML döndür.
    - <html>, <head>, <body> açma.
    - Uydurma finans veya astro veri üretme.
    - Bölümler kısa, net, email-uyumlu olsun.
    """

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    except Exception as err:
        err_text = str(err)
        if "no longer available to new users" in err_text or ("NOT_FOUND" in err_text and "models/" in err_text):
            print(f"\nGemini model '{GEMINI_MODEL}' is not available for this key/project.")
            print("Fix:")
            print("1) Set GEMINI_MODEL to a currently available model (for example: gemini-2.5-flash).")
            print("2) Re-run after updating the env variable/secret.")
        if (
            "PERMISSION_DENIED" in err_text
            and "generativelanguage.googleapis.com" in err_text
        ) or "SERVICE_DISABLED" in err_text:
            print("\nGemini request failed: API key project is not enabled for Generative Language API.")
            print("Fix:")
            print("1) Enable Generative Language API on the same project as the API key.")
            print("2) Rotate GitHub Actions secret GEMINI_API_KEY with the new key.")
            print("3) Wait 2-10 minutes for propagation, then re-run the workflow.")
        raise
    
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
    _log_payload_size(final_html)

    # 1. Dosyaya Yaz (Web İçin)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    
    # 2. Email Gönder
    send_email(final_html, date_str)

if __name__ == "__main__":
    generate_daily_brief()
