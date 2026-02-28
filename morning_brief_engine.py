import os
import datetime
import pytz
import smtplib
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import html
import base64
import time
from html.parser import HTMLParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
from google import genai
from string import Template
from kerykeion import AstrologicalSubjectFactory
import yfinance as yf

def _env_int(name, default, minimum=None, maximum=None):
    raw_value = os.environ.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    try:
        value = int(str(raw_value).strip())
    except ValueError:
        print(f"⚠️ {name} geçersiz ('{raw_value}'). Varsayılan değer ({default}) kullanılacak.")
        return default
    if minimum is not None and value < minimum:
        print(f"⚠️ {name} çok düşük ({value}). Alt sınır ({minimum}) kullanılacak.")
        value = minimum
    if maximum is not None and value > maximum:
        print(f"⚠️ {name} çok yüksek ({value}). Üst sınır ({maximum}) kullanılacak.")
        value = maximum
    return value

def _env_str(name, default=""):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip()

def _strip_wrapping_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1].strip()
    return value

def _normalize_todoist_token(raw_token):
    token = _strip_wrapping_quotes((raw_token or "").strip())
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token and set(token) == {"*"}:
        return ""
    return token

def _normalize_todoist_filter(raw_filter, default_filter):
    value = _strip_wrapping_quotes((raw_filter or "").strip())
    return value or default_filter

def _safe_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


class TodoistAPIError(RuntimeError):
    def __init__(self, phase, path, status=None, details=""):
        self.phase = phase
        self.path = path
        self.status = status
        self.details = details
        super().__init__(f"Todoist[{phase}] {path} status={status}: {details}")

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
EMAIL_RENDER_MODE = os.environ.get("EMAIL_RENDER_MODE") or "email-safe"
THEME_PROFILE = os.environ.get("THEME_PROFILE") or "offwhite-slate"
EMAIL_HTML_BUDGET_BYTES = _env_int("EMAIL_HTML_BUDGET_BYTES", 102400, minimum=16384, maximum=500000)
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image"
TIMEZONE = "Asia/Qatar"
USER_BIRTH_DATA = "14 Haziran 1989, 09:45 AM, Fatih, İstanbul"
CACHE_DIR = ".cache"
HEADER_IMAGE_DIR = os.path.join("assets", "headers")
HEADER_POOL_SIZE = _env_int("HEADER_POOL_SIZE", 5, minimum=1, maximum=10)
HEADER_TARGET_WIDTH = _env_int("HEADER_TARGET_WIDTH", 1360, minimum=680, maximum=3000)
HEADER_TARGET_HEIGHT = _env_int("HEADER_TARGET_HEIGHT", 440, minimum=220, maximum=1500)
FALLBACK_HERO_BG = "#374151"
TODOIST_DEFAULT_FILTER = "overdue | today"
TODOIST_API_TOKEN = _normalize_todoist_token(_env_str("TODOIST_API_TOKEN", ""))
TODOIST_FILTER = _normalize_todoist_filter(_env_str("TODOIST_FILTER", TODOIST_DEFAULT_FILTER), TODOIST_DEFAULT_FILTER)
TODOIST_MAX_ITEMS = max(10, _env_int("TODOIST_MAX_ITEMS", 10, minimum=1, maximum=20))
TODOIST_CACHE_TTL_MIN = _env_int("TODOIST_CACHE_TTL_MIN", 10, minimum=1, maximum=180)
TODOIST_API_BASE = "https://api.todoist.com/api/v1"

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
<html lang="tr" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sabah Özeti | Fatih</title>
    <style>
      body, table, td, p, a, span, div {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        line-height: 1.45;
      }
      img {
        display: block;
        border: 0;
        outline: none;
        text-decoration: none;
      }
      p {
        margin: 0 0 12px 0;
        line-height: 1.45;
      }
      .section-wrapper {
        padding: 0 0 16px 0;
      }
      .card {
        background-color: #FFFFFF;
        border: 1px solid #D0D3DC;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        line-height: 1.5;
      }
      .card-title {
        font-size: 16px;
        font-weight: 700;
        color: #1F2933;
        line-height: 1.45;
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
        margin: 0 0 10px 0;
        color: #1F2933;
        line-height: 1.5;
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
    <div style="display:none!important; mso-hide:all; max-height:0; max-width:0; overflow:hidden; opacity:0; color:transparent; font-size:1px; line-height:1px;">
      Sabah özeti: Astroloji, hava ve finans görünümü.
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#F6F6F7;">
      <tr>
        <td align="center" style="padding:0 12px 24px 12px;">
          <!--[if mso]>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="680">
            <tr>
              <td>
          <![endif]-->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:680px; width:100%;">
            <tr>
              <td style="padding:6px 14px; background-color:#D0D3DC; color:#4B5563; font-size:11px; text-align:right;">
                SON GÜNCELLEME: $gen_time (Katar)
              </td>
            </tr>
            <tr>
              <td style="padding:0; border:1px solid #D0D3DC; border-top:none; background-color:#FFFFFF; font-size:0; line-height:0; mso-line-height-rule:exactly;">
                $hero_image_markup
              </td>
            </tr>
            <tr>
              <td style="padding:10px 18px 8px 18px;">
                <p style="margin:0; font-size:12px; color:#4B5563; line-height:1.5;">
                  <a href="#odak" style="color:#2B7CAB; text-decoration:none;">🎯 Odak</a> ·
                  <a href="#hava" style="color:#2B7CAB; text-decoration:none;">🌤️ Hava</a> ·
                  <a href="#astro" style="color:#2B7CAB; text-decoration:none;">✨ Astro</a> ·
                  <a href="#karar" style="color:#2B7CAB; text-decoration:none;">🧭 Karar</a> ·
                  <a href="#is" style="color:#2B7CAB; text-decoration:none;">💼 İş</a> ·
                  <a href="#todoist" style="color:#2B7CAB; text-decoration:none;">✅ Görevler</a> ·
                  <a href="#finans" style="color:#2B7CAB; text-decoration:none;">📈 Finans</a>
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
                <p style="margin:0; font-size:12px; color:#4B5563;">Okuma süresi: ~2.5 dk</p>
                <p style="margin:6px 0 0 0; font-size:12px; color:#4B5563;">Veri tazeliği: Hava $weather_time — Todoist $todoist_time — Finans $finance_time ($market_status)</p>
                <p style="margin:8px 0 0 0; font-size:11px; color:#6B7280;">© 2026 Sabah Özeti - Fatih</p>
              </td>
            </tr>
          </table>
          <!--[if mso]>
              </td>
            </tr>
          </table>
          <![endif]-->
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
        "hero_image_markup",
        "weather_time",
        "todoist_time",
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

def _load_cache_any(name):
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
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
    required_ids = ["odak", "hava", "astro", "karar", "is", "todoist", "finans"]
    missing = [sec for sec in required_ids if f'id="{sec}"' not in raw_html]
    if not missing:
        return raw_html
    fallback_blocks = []
    for sec in missing:
        fallback_blocks.append(
            f'<div class="section-wrapper" id="{sec}"><div class="card"><p>Bu bölüm şu an üretilemedi. Lütfen tekrar deneyin.</p></div></div>'
        )
    return raw_html + "\n" + "\n".join(fallback_blocks)

def _replace_section_by_id(raw_html, section_id, replacement_html):
    pattern = re.compile(
        rf'<div[^>]*id=["\']{re.escape(section_id)}["\'][^>]*>',
        flags=re.IGNORECASE,
    )
    match = pattern.search(raw_html)
    if not match:
        return raw_html + "\n" + replacement_html

    token_pattern = re.compile(r"<div\b[^>]*>|</div>", flags=re.IGNORECASE)
    depth = 1
    scan_pos = match.end()
    while depth > 0:
        token = token_pattern.search(raw_html, scan_pos)
        if not token:
            break
        token_text = token.group(0).lower()
        if token_text.startswith("</div"):
            depth -= 1
        else:
            depth += 1
        scan_pos = token.end()

    return raw_html[:match.start()] + replacement_html + raw_html[scan_pos:]


def _todoist_rows_html(items):
    if not items:
        return (
            '<tr><td colspan="4" style="padding:8px; border:1px solid #D0D3DC; '
            'font-size:13px; color:#4B5563; background-color:#FFFFFF;">Bu kategori için görev yok.</td></tr>'
        )

    rows = []
    for index, item in enumerate(items):
        task_name = html.escape(item.get("content") or "-")
        project = html.escape(item.get("project") or "Genel")
        due_text = html.escape(item.get("due_text") or "Tarihsiz")
        priority = html.escape(item.get("priority") or "P4")
        row_bg = "#FFFFFF" if index % 2 == 0 else "#F8FAFC"
        row = (
            "<tr>"
            f'<td style="padding:8px; border:1px solid #D0D3DC; font-size:13px; color:#1F2933; background-color:{row_bg};">{task_name}</td>'
            f'<td style="padding:8px; border:1px solid #D0D3DC; font-size:12px; color:#4B5563; background-color:{row_bg};">{project}</td>'
            f'<td style="padding:8px; border:1px solid #D0D3DC; font-size:12px; color:#4B5563; background-color:{row_bg};">{due_text}</td>'
            f'<td style="padding:8px; border:1px solid #D0D3DC; font-size:12px; color:#4B5563; text-align:center; background-color:{row_bg};">{priority}</td>'
            "</tr>"
        )
        rows.append(row)
    return "".join(rows)


def _build_todoist_section_html(todoist_struct, todoist_time_display):
    struct = todoist_struct if isinstance(todoist_struct, dict) else {}
    total_matched = struct.get("total_matched", 0)
    displayed = struct.get("displayed_count", 0)
    overdue_count = struct.get("overdue_count", 0)
    today_count = struct.get("today_count", 0)
    timed_today_count = struct.get("timed_today_count", 0)
    overdue_items = struct.get("overdue_items", [])
    today_items = struct.get("today_items", [])
    if not isinstance(overdue_items, list):
        overdue_items = []
    if not isinstance(today_items, list):
        today_items = []

    table_style = (
        "width:100%; border-collapse:collapse; border-spacing:0; "
        "margin:8px 0 12px 0; background-color:#F6F6F7;"
    )
    header_cell = (
        "padding:8px; border:1px solid #D0D3DC; background-color:#EEF4F8; "
        "font-size:12px; font-weight:700; color:#1F2933;"
    )

    return f"""
<div class="section-wrapper" id="todoist">
  <div class="card">
    <div class="card-header" style="margin-bottom:10px;">
      <span class="tag tag-lavender">TODOIST</span>
      <span class="card-title" style="margin-left:8px;">Görev Durumu</span>
    </div>
    <p style="margin:0 0 8px 0; font-size:12px; color:#4B5563;">Veri zamanı: {html.escape(todoist_time_display)} (Asia/Qatar)</p>
    <p style="margin:0 0 10px 0; font-size:13px; color:#1F2933;">
      Toplam görev (filtre): <strong>{total_matched}</strong> · Gösterilen: <strong>{displayed}</strong> ·
      Gecikmiş: <strong style="color:#EE763A;">{overdue_count}</strong> ·
      Bugün: <strong style="color:#2B7CAB;">{today_count}</strong> ·
      Saatli etkinlik: <strong>{timed_today_count}</strong>
    </p>

    <p style="margin:0 0 6px 0;"><span class="tag tag-red">Gecikmiş</span></p>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="{table_style}">
      <tr>
        <td style="{header_cell}">Görev</td>
        <td style="{header_cell}">Proje</td>
        <td style="{header_cell}">Zaman</td>
        <td style="{header_cell}; text-align:center;">Öncelik</td>
      </tr>
      {_todoist_rows_html(overdue_items)}
    </table>

    <p style="margin:0 0 6px 0;"><span class="tag tag-blue">Bugün</span></p>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="{table_style}">
      <tr>
        <td style="{header_cell}">Görev</td>
        <td style="{header_cell}">Proje</td>
        <td style="{header_cell}">Zaman</td>
        <td style="{header_cell}; text-align:center;">Öncelik</td>
      </tr>
      {_todoist_rows_html(today_items)}
    </table>
  </div>
</div>
""".strip()


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
    print(f"📦 HTML içeriği boyutu: {payload} bayt")
    if payload > EMAIL_HTML_BUDGET_BYTES:
        print(
            f"⚠️ HTML içeriği bütçeyi aşıyor ({EMAIL_HTML_BUDGET_BYTES} bayt). "
            "Bazı istemciler uzun e-postaları kesebilir."
        )


def _strip_html_tags(raw_html):
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</(p|div|li|h2|h3|h4)>", "\n", text)
    text = re.sub(r"(?i)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _extract_themes(raw_html, limit=5):
    text = _strip_html_tags(raw_html).lower()
    words = re.findall(r"[a-zçğıöşü]{4,}", text, flags=re.IGNORECASE)
    stop = {
        "içinde", "olarak", "günün", "genel", "ancak", "birlikte", "şimdi", "çünkü",
        "sonra", "kadar", "daha", "gibi", "çok", "yine", "olan", "olanlar", "için",
        "bölüm", "bugün", "yarın", "şu", "ile", "veya", "hem", "değil", "olur",
        "olabilir", "kısa", "net", "gerek", "notlar", "veri", "zamanı", "fatih",
    }
    counts = {}
    for word in words:
        if word in stop:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [item[0] for item in ranked[:limit]]


MOOD_PROFILES = {
    1: {"label": "Çok Pozitif", "tone": "parlak, iyimser, neşeli", "overlay": "#14532D", "accent": "#26B46D"},
    2: {"label": "Pozitif-Dengeli", "tone": "ferah, dengeli, güven veren", "overlay": "#1E3A5F", "accent": "#6EB6E8"},
    3: {"label": "Nötr-Odak", "tone": "sakin, odaklı, modern", "overlay": "#374151", "accent": "#6B7280"},
    4: {"label": "Temkinli", "tone": "dikkatli, kontrollü, uyanık", "overlay": "#4B2E1F", "accent": "#EE763A"},
    5: {"label": "Uyarı", "tone": "yüksek kontrast, alarm değil ama net uyarı", "overlay": "#3B1F1F", "accent": "#EE763A"},
}

POSITIVE_WORDS = {
    "pozitif", "uyum", "destek", "rahat", "akış", "fırsat", "başarı", "kazanç",
    "iyimser", "umut", "güçlü", "ilerleme", "netlik", "bereket", "artış",
}
WARNING_WORDS = {
    "dikkat", "risk", "kaçın", "temkin", "gerilim", "belirsiz", "stres", "zor",
    "engel", "dalgalı", "hata", "tansiyon", "uyarı", "acele", "çatışma",
}


def _score_brief_mood(raw_html):
    text = _strip_html_tags(raw_html).lower()
    score = 0
    for word in POSITIVE_WORDS:
        score += text.count(word)
    for word in WARNING_WORDS:
        score -= text.count(word)

    if score >= 6:
        level = 1
    elif score >= 3:
        level = 2
    elif score >= -1:
        level = 3
    elif score >= -4:
        level = 4
    else:
        level = 5

    profile = MOOD_PROFILES[level].copy()
    profile["level"] = level
    profile["score"] = score
    return profile


def _extract_image_payload(response):
    parts = []
    if getattr(response, "parts", None):
        parts.extend(response.parts)

    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if content and getattr(content, "parts", None):
            parts.extend(content.parts)

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if not inline:
            continue
        data = getattr(inline, "data", None)
        if not data:
            continue
        mime = getattr(inline, "mime_type", None) or "image/png"
        if isinstance(data, str):
            try:
                return base64.b64decode(data), mime
            except Exception:
                continue
        if isinstance(data, (bytes, bytearray)):
            return bytes(data), mime
    return None, None


def _image_extension_for_mime(mime):
    if mime == "image/jpeg":
        return "jpg"
    if mime == "image/webp":
        return "webp"
    return "png"


def _header_reference_dimensions():
    reference = os.path.join(HEADER_IMAGE_DIR, "mood-5-5.png")
    if os.path.exists(reference):
        try:
            with Image.open(reference) as img:
                w, h = img.size
            if w > 0 and h > 0:
                return w, h
        except Exception as err:
            print(f"⚠️ Header referans ölçüsü okunamadı ({reference}): {err}")
    return HEADER_TARGET_WIDTH, HEADER_TARGET_HEIGHT


def _normalize_header_image(image_path, target_w, target_h):
    try:
        with Image.open(image_path) as src:
            src_w, src_h = src.size
            if src_w <= 0 or src_h <= 0:
                return

            target_ratio = target_w / float(target_h)
            src_ratio = src_w / float(src_h)

            if src_ratio > target_ratio:
                crop_h = src_h
                crop_w = int(round(crop_h * target_ratio))
            else:
                crop_w = src_w
                crop_h = int(round(crop_w / target_ratio))

            left = max(0, (src_w - crop_w) // 2)
            top = max(0, (src_h - crop_h) // 2)
            right = min(src_w, left + crop_w)
            bottom = min(src_h, top + crop_h)

            cropped = src.crop((left, top, right, bottom))
            resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

            extension = os.path.splitext(image_path)[1].lower()
            if extension in (".jpg", ".jpeg"):
                resized = resized.convert("RGB")
                resized.save(image_path, format="JPEG", quality=92, optimize=True)
            elif extension == ".webp":
                resized = resized.convert("RGB")
                resized.save(image_path, format="WEBP", quality=92, method=6)
            else:
                if resized.mode not in ("RGB", "RGBA"):
                    resized = resized.convert("RGBA")
                resized.save(image_path, format="PNG", optimize=True)
    except Exception as err:
        print(f"⚠️ Header normalizasyonu başarısız ({image_path}): {err}")


def _normalize_mood_header_variants(mood_level, target_w, target_h):
    variants = _existing_mood_header_variants(mood_level)
    for _, image_path in sorted(variants.items()):
        _normalize_header_image(image_path, target_w, target_h)
    return variants


def _build_header_image_prompt(mood, raw_html, date_str, variant_index):
    themes = _extract_themes(raw_html, limit=5)
    theme_text = ", ".join(themes) if themes else "astroloji, finans, hava, odak"
    return f"""
Türkçe sabah özeti için modern ve soyut bir kapak görseli üret.
Tarih bağlamı: {date_str}
Gün ruh hali: {mood['label']} (ton: {mood['tone']}).
Temalar: {theme_text}.
Varyasyon kimliği: set-{variant_index}

Kurallar:
- Yatay oran: 680x220 (yaklaşık 3.09:1) düşün ve kompozisyonu bu orana göre kur.
- Görsel soyut olsun; fotoğrafik yüz/insan olmasın.
- Yazı, harf, logo, watermark, sembol, sayı, rakam, tipografi, ikon metni üretme.
- Renk seti: off-white, slate mist, sıcak turuncu vurgu, canlı yeşil, gökyüzü mavisi.
- Kontrast yüksek ama göz yormayan, premium hissiyat.
- Parlaklık ruh hali seviyesine göre ayarlansın.
- Görsel tam dolgu (full-bleed) olsun; üst/alt/yan kenarlarda beyaz veya boş bant bırakma.
"""


def _hero_image_public_url(image_path):
    repo = os.environ.get("GITHUB_REPOSITORY") or "ustunfatih/morning-brief"
    branch = os.environ.get("GITHUB_REF_NAME") or "main"
    rel_path = image_path.replace(os.sep, "/")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel_path}?v={stamp}"


def _build_hero_image_markup(image_url, mood, date_str, todoist_struct=None):
    struct = todoist_struct if isinstance(todoist_struct, dict) else {}
    task_count = _safe_int(struct.get("displayed_count"), 0)
    overdue_count = _safe_int(struct.get("overdue_count"), 0)
    today_count = _safe_int(struct.get("today_count"), 0)
    mood_score = mood.get("level", 3)
    badge_style = (
        "display:inline-block; margin:0 0 8px 0; font-size:12px; color:#FFFFFF; "
        "background-color:#1F2933; border:1px solid #FFFFFF; "
        "border-radius:8px; padding:4px 8px; line-height:1.25;"
    )
    mood_badge_style = (
        "display:inline-block; margin:0 0 8px 8px; font-size:12px; color:#FFFFFF; "
        "background-color:#111827; border:1px solid #FFFFFF; "
        "border-radius:8px; padding:4px 8px; line-height:1.25;"
    )
    task_badge_style = (
        "display:inline-block; margin:0 0 8px 8px; font-size:12px; color:#FFFFFF; "
        "background-color:#0F766E; border:1px solid #FFFFFF; "
        "border-radius:8px; padding:4px 8px; line-height:1.25;"
    )
    task_badge_text = f"Görev: {task_count} · Gecikmiş: {overdue_count} · Bugün: {today_count}"
    title_style = (
        "margin:0; font-size:30px; line-height:1.25; font-weight:800; color:#FFFFFF; "
        "text-shadow:0 2px 8px rgba(0,0,0,0.55); mso-line-height-rule:exactly;"
    )
    subtitle_style = (
        "margin:6px 0 0 0; font-size:13px; color:#F6F6F7; "
        "text-shadow:0 1px 4px rgba(0,0,0,0.45); line-height:1.35; mso-line-height-rule:exactly;"
    )
    text_wrap_style = (
        "display:inline-block; background-color:#1F2933; background-color:rgba(31,41,51,0.55); "
        "padding:10px 12px; border-radius:10px; font-size:16px; line-height:1.45;"
    )

    if not image_url:
        return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
  <tr>
    <td align="left" valign="top" style="height:220px; background-color:{FALLBACK_HERO_BG}; font-size:0; line-height:0; mso-line-height-rule:exactly; overflow:hidden;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="height:220px; border-collapse:collapse;">
        <tr>
          <td align="left" valign="bottom" style="padding:18px; font-size:14px; line-height:1.3;">
            <div style="{text_wrap_style}">
              <p style="{badge_style}">📅 {date_str}</p><span style="{mood_badge_style}">Ruh Skoru: {mood_score}/5</span><span style="{task_badge_style}">{task_badge_text}</span>
              <p style="{title_style}">Günaydın, Fatih.</p>
              <p style="{subtitle_style}">📍 Doha, Katar · {mood['label']}</p>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
""".strip()

    background_style = (
        f"height:220px; vertical-align:top; "
        f"background-color:{mood['overlay']}; "
        f"background-image:url('{image_url}'); background-size:cover; background-position:center center; background-repeat:no-repeat; "
        f"font-size:0; line-height:0; mso-line-height-rule:exactly; overflow:hidden;"
    )
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt;">
  <tr>
    <td background="{image_url}" bgcolor="{mood['overlay']}" align="left" valign="top" style="{background_style}">
      <!--[if gte mso 9]>
      <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:680px;height:220px;">
        <v:fill type="frame" aspect="atleast" src="{image_url}" color="{mood['overlay']}" />
        <v:textbox inset="0,0,0,0">
      <![endif]-->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="height:220px; border-collapse:collapse;">
        <tr>
          <td align="left" valign="bottom" style="padding:18px; font-size:14px; line-height:1.3;">
            <div style="{text_wrap_style}">
              <p style="{badge_style}">📅 {date_str}</p><span style="{mood_badge_style}">Ruh Skoru: {mood_score}/5</span><span style="{task_badge_style}">{task_badge_text}</span>
              <p style="{title_style}">Günaydın, Fatih.</p>
              <p style="{subtitle_style}">📍 Doha, Katar · {mood['label']}</p>
            </div>
          </td>
        </tr>
      </table>
      <!--[if gte mso 9]>
        </v:textbox>
      </v:rect>
      <![endif]-->
    </td>
  </tr>
</table>
""".strip()


def _existing_mood_header_variants(mood_level):
    if not os.path.isdir(HEADER_IMAGE_DIR):
        return {}
    pattern = re.compile(rf"^mood-{mood_level}-(\d+)\.(png|jpg|webp)$", flags=re.IGNORECASE)
    variants = {}
    for filename in os.listdir(HEADER_IMAGE_DIR):
        match = pattern.match(filename)
        if not match:
            continue
        variant_index = _safe_int(match.group(1), -1)
        if variant_index < 1:
            continue
        variants[variant_index] = os.path.join(HEADER_IMAGE_DIR, filename)
    return variants


def _header_model_candidates():
    requested = os.environ.get("GEMINI_IMAGE_MODEL")
    model_candidates = []
    if requested:
        model_candidates.append(requested)
    model_candidates.extend([GEMINI_IMAGE_MODEL, "gemini-3.1-flash-image-preview"])
    seen = set()
    return [m for m in model_candidates if not (m in seen or seen.add(m))]


def _ensure_mood_header_pool(client, mood, raw_html, date_str):
    mood_level = _safe_int(mood.get("level"), 3)
    target_w, target_h = _header_reference_dimensions()
    variants = _normalize_mood_header_variants(mood_level, target_w, target_h)
    if len(variants) >= HEADER_POOL_SIZE:
        return variants, "pool-cache"

    os.makedirs(HEADER_IMAGE_DIR, exist_ok=True)
    used_model = ""
    for variant_index in range(1, HEADER_POOL_SIZE + 1):
        if variant_index in variants:
            continue

        prompt = _build_header_image_prompt(mood, raw_html, date_str, variant_index)
        generated = False
        for model_name in _header_model_candidates():
            try:
                response = client.models.generate_content(model=model_name, contents=[prompt])
                image_bytes, mime = _extract_image_payload(response)
                if not image_bytes:
                    continue
                ext = _image_extension_for_mime(mime)
                image_path = os.path.join(HEADER_IMAGE_DIR, f"mood-{mood_level}-{variant_index}.{ext}")
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                _normalize_header_image(image_path, target_w, target_h)
                variants[variant_index] = image_path
                used_model = model_name
                generated = True
                print(f"🖼️ Mood header üretildi ({model_name}) -> {image_path}")
                break
            except Exception as err:
                print(f"⚠️ Mood header üretimi başarısız ({model_name}, varyasyon {variant_index}): {err}")
        if not generated:
            print(f"⚠️ Mood={mood_level} varyasyon={variant_index} üretilemedi.")
    variants = _normalize_mood_header_variants(mood_level, target_w, target_h)
    return variants, used_model


def _select_mood_header_path(variants, now_qatar):
    if not variants:
        return ""
    ordered = [variants[key] for key in sorted(variants.keys())]
    day_key = now_qatar.toordinal()
    selected_index = day_key % len(ordered)
    return ordered[selected_index]


def _generate_daily_header_image(client, raw_html, date_str, mood, now_qatar):
    variants, model_used = _ensure_mood_header_pool(client, mood, raw_html, date_str)
    selected_path = _select_mood_header_path(variants, now_qatar.date())
    if selected_path:
        return _hero_image_public_url(selected_path), model_used or "pool-cache"
    return "", ""

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
    msg["Subject"] = f"Sabah Özeti: {date_str}"
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
    "sunny": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2600.png", "Güneşli"),
    "partly-cloudy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26c5.png", "Parçalı bulutlu"),
    "cloudy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2601.png", "Bulutlu"),
    "rainy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f327.png", "Yağmurlu"),
    "stormy": ("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26c8.png", "Fırtınalı"),
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

                direction = "yukarı" if change_pct >= 0 else "aşağı"
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


def _parse_iso_datetime(value):
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed
    except Exception:
        return None


def _todoist_request(path, params=None, allow_retry=True, phase="request"):
    if not TODOIST_API_TOKEN:
        raise TodoistAPIError(phase=phase, path=path, status=401, details="TODOIST_API_TOKEN bulunamadı veya geçersiz.")

    query = urllib.parse.urlencode(params or {})
    url = f"{TODOIST_API_BASE}{path}"
    if query:
        url = f"{url}?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TODOIST_API_TOKEN}",
            "User-Agent": "MorningBrief/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="ignore")
        if err.code == 429 and allow_retry:
            wait_seconds = _safe_int(err.headers.get("Retry-After"), 2)
            wait_seconds = max(1, min(wait_seconds, 15))
            print(f"⚠️ Todoist[phase={phase}] hız sınırı ({path}): {wait_seconds} sn sonra tekrar denenecek.")
            time.sleep(wait_seconds)
            return _todoist_request(path, params=params, allow_retry=False, phase=phase)
        raise TodoistAPIError(phase=phase, path=path, status=err.code, details=body[:180])
    except Exception as err:
        raise TodoistAPIError(phase=phase, path=path, details=str(err))

def _todoist_results(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return results
    return []

def _parse_todoist_due(due_obj, qatar_tz, now_qatar):
    due = due_obj or {}
    due_raw = (due.get("date") or "").strip()
    due_tz_name = (due.get("timezone") or "").strip()

    due_text = "Tarihsiz"
    is_overdue = False
    has_time = False
    is_today = False
    due_sort = float("inf")

    if not due_raw:
        return due_text, due_sort, is_overdue, has_time, is_today

    if "T" in due_raw:
        try:
            parsed_dt = datetime.datetime.fromisoformat(due_raw)
            if parsed_dt.tzinfo is None:
                if due_tz_name:
                    due_tz = pytz.timezone(due_tz_name)
                    due_local = due_tz.localize(parsed_dt).astimezone(qatar_tz)
                else:
                    due_local = qatar_tz.localize(parsed_dt)
            else:
                due_local = parsed_dt.astimezone(qatar_tz)
            due_text = due_local.strftime("%d.%m %H:%M")
            due_sort = due_local.timestamp()
            is_overdue = due_local < now_qatar
            has_time = due_local.date() == now_qatar.date()
            is_today = due_local.date() == now_qatar.date()
            return due_text, due_sort, is_overdue, has_time, is_today
        except Exception:
            pass

    try:
        due_date = datetime.date.fromisoformat(due_raw[:10])
        due_text = due_date.strftime("%d.%m")
        is_overdue = due_date < now_qatar.date()
        is_today = due_date == now_qatar.date()
        due_midday = qatar_tz.localize(datetime.datetime(due_date.year, due_date.month, due_date.day, 12, 0))
        due_sort = due_midday.timestamp()
        return due_text, due_sort, is_overdue, has_time, is_today
    except Exception:
        return due_raw, due_sort, is_overdue, has_time, is_today


def get_todoist_data(now_qatar):
    """Fetch today's Todoist tasks/events in a non-blocking way."""
    now_utc_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    empty_struct = {
        "total_matched": 0,
        "displayed_count": 0,
        "overdue_count": 0,
        "today_count": 0,
        "timed_today_count": 0,
        "overdue_items": [],
        "today_items": [],
    }
    if not TODOIST_API_TOKEN:
        return "(Todoist bağlantısı yapılandırılmamış.)", now_utc_iso, empty_struct

    fresh_cache = _load_cache("todoist.json", ttl_minutes=TODOIST_CACHE_TTL_MIN)
    if fresh_cache:
        cached_data = fresh_cache.get("data", {}) if isinstance(fresh_cache, dict) else {}
        cached_struct = cached_data.get("structured")
        if cached_data.get("text") and cached_data.get("fetched_at") and isinstance(cached_struct, dict):
            return cached_data["text"], cached_data["fetched_at"], cached_struct
        if cached_data.get("text") and cached_data.get("fetched_at"):
            print("⚠️ Todoist[phase=cache_read] önbellekte structured alanı yok, canlı veriye geçiliyor.")
        else:
            print("⚠️ Todoist[phase=cache_read] güncel önbellek yapısı bozuk, canlı veriye geçiliyor.")

    stale_cache = _load_cache_any("todoist.json")
    priority_map = {4: "P1", 3: "P2", 2: "P3", 1: "P4"}
    qatar_tz = pytz.timezone(TIMEZONE)
    token_preview = f"{TODOIST_API_TOKEN[:4]}...{TODOIST_API_TOKEN[-3:]}" if len(TODOIST_API_TOKEN) >= 8 else "kısa-token"
    print(f"ℹ️ Todoist[phase=init] entegrasyon aktif. Token: {token_preview}, filtre: '{TODOIST_FILTER}'")

    try:
        filter_candidates = []
        for item in [TODOIST_FILTER, TODOIST_DEFAULT_FILTER, "today"]:
            candidate = (item or "").strip()
            if candidate and candidate not in filter_candidates:
                filter_candidates.append(candidate)

        tasks = None
        selected_filter = None
        last_task_error = None
        for candidate_filter in filter_candidates:
            try:
                task_payload = _todoist_request(
                    "/tasks/filter",
                    params={"query": candidate_filter},
                    phase="tasks_fetch",
                )
                tasks = _todoist_results(task_payload)
                selected_filter = candidate_filter
                break
            except TodoistAPIError as err:
                last_task_error = err
                if err.status == 400:
                    print(
                        f"⚠️ Todoist[phase=tasks_fetch] filtre geçersiz ('{candidate_filter}'). "
                        "Alternatif filtre deneniyor."
                    )
                    continue
                raise

        if tasks is None:
            raise last_task_error or TodoistAPIError(
                phase="tasks_fetch",
                path="/tasks/filter",
                details="Görev listesi alınamadı.",
            )

        print(f"✅ Todoist[phase=tasks_fetch] {len(tasks)} görev alındı. Kullanılan filtre: '{selected_filter}'")

        project_map = {}
        try:
            projects_payload = _todoist_request("/projects", phase="projects_fetch")
            projects = _todoist_results(projects_payload)
            project_map = {
                str(item.get("id")): item.get("name", "Genel")
                for item in projects
                if isinstance(item, dict)
            }
        except TodoistAPIError as err:
            print(
                f"⚠️ Todoist[phase=projects_fetch] proje adları alınamadı "
                f"(status={err.status}). Görevler proje kimliğiyle devam edecek."
            )

        normalized = []
        for task in tasks:
            try:
                if not isinstance(task, dict):
                    continue
                content = (task.get("content") or "").strip()
                if not content:
                    continue
                if len(content) > 120:
                    content = content[:117] + "..."

                due_text, due_sort, is_overdue, has_time, is_today = _parse_todoist_due(task.get("due"), qatar_tz, now_qatar)

                priority_num = _safe_int(task.get("priority"), 1)
                project_id = str(task.get("project_id") or "")
                default_project_label = f"Proje {project_id}" if project_id else "Genel"
                normalized.append({
                    "content": content,
                    "priority": priority_map.get(priority_num, "P4"),
                    "priority_num": priority_num,
                    "project": project_map.get(project_id, default_project_label),
                    "due_text": due_text,
                    "due_sort": due_sort,
                    "is_overdue": is_overdue,
                    "has_time": has_time,
                    "is_today": is_today,
                })
            except Exception as err:
                print(f"⚠️ Todoist[phase=normalize] bir görev atlandı: {err}")
                continue

        normalized.sort(key=lambda item: (0 if item["is_overdue"] else 1, item["due_sort"], -item["priority_num"]))
        total_matched = len(normalized)
        max_items = max(1, TODOIST_MAX_ITEMS)
        overdue_all = [item for item in normalized if item["is_overdue"]]
        today_all = [item for item in normalized if item.get("is_today") and not item["is_overdue"]]
        other_all = [item for item in normalized if not item["is_overdue"] and not item.get("is_today")]

        selected_items = []
        for bucket in (overdue_all, today_all, other_all):
            for item in bucket:
                if len(selected_items) >= max_items:
                    break
                selected_items.append(item)
            if len(selected_items) >= max_items:
                break

        overdue_items = [item for item in selected_items if item["is_overdue"]]
        today_items = [item for item in selected_items if item.get("is_today") and not item["is_overdue"]]

        overdue_count = sum(1 for item in selected_items if item["is_overdue"])
        today_count = sum(1 for item in selected_items if item.get("is_today") and not item["is_overdue"])
        timed_today_count = sum(1 for item in selected_items if item["has_time"])

        summary = (
            f"  Toplam görev (filtre): {total_matched} | Gösterilen: {len(selected_items)} | "
            f"Bugün saatli etkinlik: {timed_today_count} | "
            f"Gecikmiş: {overdue_count}"
        )

        lines = []
        for item in selected_items:
            overdue_mark = " (Gecikmiş)" if item["is_overdue"] else ""
            lines.append(
                f"  - [{item['priority']}] {item['content']} | {item['project']} | {item['due_text']}{overdue_mark}"
            )

        if not lines:
            lines.append("  - Filtreye göre bugün için görev bulunmadı.")

        text = "GERÇEK TODOIST GÖREVLERİ:\n" + summary + "\n\nGörev listesi:\n" + "\n".join(lines)
        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        structured = {
            "total_matched": total_matched,
            "displayed_count": len(selected_items),
            "overdue_count": overdue_count,
            "today_count": today_count,
            "timed_today_count": timed_today_count,
            "overdue_items": overdue_items,
            "today_items": today_items,
        }
        _save_cache("todoist.json", {"text": text, "fetched_at": fetched_at, "structured": structured})
        return text, fetched_at, structured
    except Exception as err:
        if isinstance(err, TodoistAPIError):
            if err.status in (401, 403):
                print(
                    f"⚠️ Todoist[phase={err.phase}] erişim reddedildi (status={err.status}). "
                    "Token değeri düz metin olmalı; 'Bearer ' öneki veya tırnak içermemeli."
                )
            elif err.status == 400:
                print(
                    f"⚠️ Todoist[phase={err.phase}] geçersiz istek (status=400). "
                    f"Filtreyi kontrol et: '{TODOIST_FILTER}'."
                )
            elif err.status in (429, 500, 502, 503, 504):
                print(
                    f"⚠️ Todoist[phase={err.phase}] geçici servis hatası (status={err.status}). "
                    "Bir sonraki çalıştırmada otomatik düzelebilir."
                )
            else:
                print(f"⚠️ Todoist[phase={err.phase}] hata (status={err.status}): {err.details}")
        else:
            print(f"⚠️ Todoist[phase=unknown] veri hatası: {err}")
        if stale_cache and isinstance(stale_cache, dict):
            cached_data = stale_cache.get("data", {})
            if cached_data.get("text") and cached_data.get("fetched_at"):
                print("ℹ️ Todoist[phase=cache_fallback] son geçerli önbellek kullanılıyor.")
                cached_struct = cached_data.get("structured")
                if not isinstance(cached_struct, dict):
                    cached_struct = empty_struct
                return cached_data["text"], cached_data["fetched_at"], cached_struct
        return "(Todoist verisi alınamadı.)", now_utc_iso, empty_struct


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
GERÇEK GEZEGENSEL VERİLER (Swiss Ephemeris - bugünkü hesaplama):

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
        return "\n(Efemeris verisi hesaplanamadı, genel astroloji bilgisi kullan.)\n"


def generate_daily_brief():
    if not API_KEY:
        print("Hata: GEMINI_API_KEY (veya GOOGLE_API_KEY) bulunamadı.")
        return

    _validate_html_template_placeholders()

    client = genai.Client(api_key=API_KEY)
    print(f"Kullanılan Gemini modeli: {GEMINI_MODEL}")
    
    # Time Calc
    now_qatar = get_current_time_qatar()
    date_str = format_date_str(now_qatar)
    gen_time_str = now_qatar.strftime("%H:%M:%S")

    print(f"Özet oluşturuluyor: {date_str}...")

    # Compute real planetary positions
    planetary_data = get_planetary_data(now_qatar)

    # Fetch real financial data
    financial_data, finance_fetched_at, finance_latest_ts = get_financial_data()

    # Fetch weather forecast
    weather_data, weather_icon_key, weather_fetched_at = get_weather_data()
    weather_icon_html = _weather_icon_image_html(weather_icon_key)

    # Fetch Todoist tasks/events
    todoist_data, todoist_fetched_at, todoist_struct = get_todoist_data(now_qatar)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    market_status = _market_status_us(now_utc)
    weather_time_display = _format_time_for_display(datetime.datetime.fromisoformat(weather_fetched_at), TIMEZONE)
    finance_time_display = _format_time_for_display(datetime.datetime.fromisoformat(finance_latest_ts), "US/Eastern")
    todoist_time_display = _format_time_for_display(datetime.datetime.fromisoformat(todoist_fetched_at), TIMEZONE)

    if EMAIL_RENDER_MODE != "email-safe":
        print(f"⚠️ Desteklenmeyen EMAIL_RENDER_MODE='{EMAIL_RENDER_MODE}'. email-safe moduna dönülüyor.")
    if THEME_PROFILE != "offwhite-slate":
        print(f"⚠️ Desteklenmeyen THEME_PROFILE='{THEME_PROFILE}'. offwhite-slate profiline dönülüyor.")
    print(f"E-posta render modu: {EMAIL_RENDER_MODE} | Tema: {THEME_PROFILE}")

    # --- ENRICHED PROMPT WITH REAL EPHEMERIS DATA ---
    prompt = f"""
    Sen Fatih için "Sabah Özeti" hazırlayan, zeki ama net bir astroloji ve finans asistanısın.

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
    - script, svg, canvas, iframe, form ve style etiketi kullanma.
    - CSS custom property kullanma.
    - Flex veya grid layout kullanma.
    - Tek kolon, email-uyumlu sade bloklar kullan.
    - Karmaşık animasyon, sticky, hover davranışı istemiyoruz.

    GERÇEK VERİLER:
    {planetary_data}
    {financial_data}
    {weather_data}
    {todoist_data}

    PORTFÖY:
    - İzinli liste: QQQI, FDVV, SCHD, SCHG, IAUI, SLV
    - Hariç tutulanlar: YMAG, TQQQ, GLDW

    ASTROLOJİ KAYNAKLARI:
    {ASTROLOGER_SOURCES}
    {ASTROLOGY_BOOKS}

    BÖLÜMLER:
    1) ODAK (id=odak):
       - Bir motto, 3 kelime kuralı, kısa ruh hali geçiş analizi.
       - kart bloğu (card) içinde olsun.

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
       - Bir "Astro-Bilişsel Uyarı" kartı ekle (açık mavi-slate tonunda).

    4) KARAR (id=karar):
       - En iyi, nötr, kaçın alanları.
       - decision-grid içinde 3 adet decision-box; hepsi dikey okunabilir olsun.

    5) İŞ (id=is):
       - <ul class="bullet-list"> ile kısa maddeler.

    6) TODOIST (id=todoist):
       - card içinde kısa bir görev özeti ver.
       - <ul class="bullet-list"> kullanarak en önemli görevleri listele.
       - Her maddede görev adı + proje + saat/tarih bilgisi olsun.
       - Başta veri zamanı satırı:
         "Veri zamanı: {todoist_time_display} (Asia/Qatar)"
       - "Saatli etkinlikler" varsa ayrı bir kısa paragrafla vurgula.

    7) FİNANS (id=finans):
       - Gerçek fiyat + değişim yüzdesi.
       - Her hisse için davranışsal not.
       - Hisse adını <span class="ticker-pill"> ile yaz.
       - Başta veri zamanı satırı:
         "Veri zamanı: {finance_time_display} (US/Eastern) — {market_status}"
       - Liste yapısı: <ul class="finance-list"><li>...</li></ul>

    8) TEK SORU:
       - Günün düşündürücü sorusu.

    KURALLAR:
    - Yalnızca saf HTML döndür.
    - <html>, <head>, <body> açma.
    - Uydurma finans, astroloji veya Todoist görevi üretme.
    - Türkçe karakterleri ve yazım kurallarını doğru kullan.
    - Bölümler kısa, net, email-uyumlu olsun.
    """

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    except Exception as err:
        err_text = str(err)
        if "no longer available to new users" in err_text or ("NOT_FOUND" in err_text and "models/" in err_text):
            print(f"\nGemini modeli '{GEMINI_MODEL}' bu anahtar/proje için kullanılamıyor.")
            print("Çözüm:")
            print("1) GEMINI_MODEL değişkenini kullanılabilir güncel bir modelle ayarla (örnek: gemini-2.5-flash).")
            print("2) Ortam değişkeni/secret güncelledikten sonra workflow'u tekrar çalıştır.")
        if (
            "PERMISSION_DENIED" in err_text
            and "generativelanguage.googleapis.com" in err_text
        ) or "SERVICE_DISABLED" in err_text:
            print("\nGemini isteği başarısız: API anahtarının bağlı olduğu projede Generative Language API etkin değil.")
            print("Çözüm:")
            print("1) API anahtarının bulunduğu aynı projede Generative Language API'yi etkinleştir.")
            print("2) GitHub Actions içindeki GEMINI_API_KEY secret değerini yeni anahtarla güncelle.")
            print("3) Yayılım için 2-10 dakika bekleyip workflow'u tekrar çalıştır.")
        raise
    
    # Temizlik
    raw_html = response.text.replace("```html", "").replace("```", "").strip()
    raw_html = _sanitize_html(raw_html)
    raw_html = _escape_template_like_sequences(raw_html)
    raw_html = _ensure_required_sections(raw_html)
    todoist_section_html = _build_todoist_section_html(todoist_struct, todoist_time_display)
    raw_html = _replace_section_by_id(raw_html, "todoist", todoist_section_html)

    mood = _score_brief_mood(raw_html)
    print(f"🧠 Özet ruh hali seviyesi: {mood['level']} ({mood['label']}) | skor={mood['score']}")
    hero_image_url, image_model_used = _generate_daily_header_image(client, raw_html, date_str, mood, now_qatar)
    if hero_image_url:
        print(f"🖼️ Üst görsel URL'si hazırlandı ({image_model_used})")
    else:
        print("⚠️ Üst görsel kullanılamadı, yedek hero bloğu kullanılıyor.")
    hero_image_markup = _build_hero_image_markup(hero_image_url, mood, date_str, todoist_struct)
    
    # Template Birleştirme
    final_html = HTML_TEMPLATE.substitute(
        date_string=date_str,
        content_body=raw_html,
        hero_image_markup=hero_image_markup,
        gen_time=gen_time_str,
        weather_time=weather_time_display,
        todoist_time=todoist_time_display,
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
