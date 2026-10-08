# Morning Brief — Yeniden Aktifleştirme Rehberi

**Durum:** Duraklatıldı (Ekim 2026). GitHub reposu kaldırıldı; proje yalnızca yerelde tutuluyor.
Bu klasör `main` dalının son halidir (tam git geçmişiyle).

## Proje ne yapıyor?
`morning_brief_engine.py` her sabah (06:00 Asia/Qatar) Gemini ile Türkçe bir "sabah özeti" üretir:
hava (Doha), astroloji (kerykeion), Todoist görevleri, portföy/piyasa özeti (yfinance + Google Sheets),
günün header görseli. Sonuç `index.html` olarak yazılır ve e-posta ile gönderilir.
GitHub Actions (`.github/workflows/daily_brief.yml`) bunu cron ile çalıştırır ve `index.html` + `assets/headers`'ı repoya commit'ler.

Önemli dosyalar: `morning_brief_engine.py`, `brief-settings.json` (gizli olmayan ayarlar),
`.env.example`, `requirements.txt`, `mockups/brief-format-dashboard.html` + `scripts/settings_server.py` (yerel ayar paneli),
`tests/test_security_hardening.py`.

## Yeniden aktifleştirme adımları

### 1) Yeni GitHub reposu
```bash
cd /Volumes/Mini/vibecoded/morning-brief
git remote set-url origin https://github.com/<kullanici>/morning-brief.git   # eski repo silindi
git push -u origin main
```
- Repo **private** olsun (kişisel portföy/doğum verisi içeriyor olabilir).
- Actions yazma izni gerekir: workflow'da `permissions: contents: write` zaten var.
- GitHub, 60 gün aktivite olmayan repolarda zamanlanmış workflow'ları devre dışı bırakır; yeniden push sonrası Actions sekmesinden etkin olduğunu kontrol et.

### 2) Secret'ları yeniden gir (Settings → Secrets and variables → Actions)
Secret'lar repo ile birlikte gitmez; **silinen repodan geri alınamaz**, hepsini yeniden oluşturman gerekir.

| Secret | Zorunlu | Not |
|---|---|---|
| `GEMINI_API_KEY` | Evet | Eski anahtar muhtemelen geçersiz; Google AI Studio'dan yenisini al. Anahtarın projesinde *Generative Language API* etkin olmalı. |
| `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO` | Evet (e-posta için) | Gmail ise uygulama şifresi (App Password) kullan. |
| `TODOIST_API_TOKEN` | Opsiyonel | Ham token; `Bearer` öneki ve tırnak yok. API v1 (`/api/v1`) kullanılıyor. |
| `GSHEETS_SPREADSHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` | Opsiyonel | JSON base64 olmalı; tabloyu service account e-postasıyla paylaş. |
| `USER_BIRTH_DATA`, `NATAL_YEAR/MONTH/DAY/HOUR/MINUTE/LAT/LNG/TZ` | Opsiyonel | Astroloji bölümü için özel doğum verisi. |

Opsiyonel **Variables:** `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL`, `EMAIL_RENDER_MODE`, `THEME_PROFILE`, `TODOIST_FILTER`, `TODOIST_MAX_ITEMS`, `TODOIST_CACHE_TTL_MIN`, `GSHEETS_SHEET_NAME`, `GSHEETS_HEADER_ROW`, `GSHEETS_READ_RANGE`, `GSHEETS_TICKER_COLUMN`, `GSHEETS_HOLDINGS_COLUMN`. Değerler için `.env.example` ve `brief-settings.json`'a bak.

### 3) Yerelde dene
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # değerleri doldur
set -a; source .env; set +a
python morning_brief_engine.py
python -m unittest tests/test_security_hardening.py   # (veya pytest)
```

### 4) Bakım kontrol listesi (uzun aradan sonra)
- [ ] **Gemini modelleri:** `gemini-2.5-flash` ve `gemini-2.5-flash-image` kullanımdan kalkmış olabilir → güncel model adlarıyla `GEMINI_MODEL` / `GEMINI_IMAGE_MODEL` ve `brief-settings.json` → `format.geminiModel` değerini güncelle. `google-genai` SDK API'si değişmiş olabilir.
- [ ] **Bağımlılıklar:** `requirements.txt` sürüm sabitlemiyor; kırılma olursa özellikle `yfinance` (sık bozulur), `kerykeion` ve `google-genai`'yi kontrol et.
- [ ] **GitHub Actions:** `actions/checkout@v4`, `actions/setup-python@v4` eskimiş olabilir (Node sürümü uyarıları); `v5+`'a yükselt.
- [ ] **Todoist:** API v1 endpoint'leri hâlâ geçerli mi kontrol et.
- [ ] **Portföy:** `brief-settings.json` içindeki `holdings` yer tutucu değerler (shares = 1); gerçek portföyü Google Sheets'ten çekiyorsan o ayarları doğrula.
- [ ] **Cron:** `0 3 * * *` UTC = 06:00 Doha (UTC+3). Konum/saat dilimi değiştiyse `daily_brief.yml` ve `data.timezone` ayarını güncelle.
- [ ] **E-posta QA:** Tasarım değiştirirsen README'deki "Email QA Matrix"i uygula.
- [ ] **Güvenlik:** Eski anahtarları/parolaları iptal et; repo geçmişinde kişisel veri (doğum bilgisi, e-posta) olup olmadığını kontrol et, yeni repoya push etmeden önce gerekirse temizle.

### 5) İlk çalıştırma
Actions → *Generate Morning Brief* → *Run workflow* ile elle tetikle, `index.html` commit'lendiğini ve e-postanın geldiğini doğrula; sonra cron'a bırak.

## Not
Bot her gün `index.html` ve `assets/headers` commit'lediği için repo geçmişi büyüdü (~50 commit). Yeni repoda temiz başlamak istersen: `rm -rf .git && git init && git add . && git commit -m "Initial import"`.
