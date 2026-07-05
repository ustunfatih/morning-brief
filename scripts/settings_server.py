#!/usr/bin/env python3
import json
import os
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "brief-settings.json"


class SettingsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/settings":
            return self._send_json(_read_settings())
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/settings":
            return self._save_settings()
        if self.path == "/api/publish":
            return self._publish_settings()
        self.send_error(404, "Unknown endpoint")

    def _read_body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _save_settings(self):
        try:
            payload = self._read_body_json()
            settings = payload.get("settings", payload)
            if not isinstance(settings, dict):
                raise ValueError("settings must be a JSON object")
            _write_settings(settings)
            self._send_json({"ok": True, "path": str(SETTINGS_PATH)})
        except Exception as err:
            self._send_json({"ok": False, "error": str(err)}, status=400)

    def _publish_settings(self):
        try:
            payload = self._read_body_json()
            settings = payload.get("settings")
            message = str(payload.get("message") or "Update morning brief settings").strip()
            if isinstance(settings, dict):
                _write_settings(settings)
            result = _git_publish(message)
            self._send_json({"ok": True, **result})
        except Exception as err:
            self._send_json({"ok": False, "error": str(err)}, status=400)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _read_settings():
    if not SETTINGS_PATH.exists():
        return {}
    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_settings(settings):
    tmp_path = SETTINGS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, SETTINGS_PATH)


def _run_git(args):
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return (completed.stdout or "").strip()


def _git_publish(message):
    _run_git(["add", "brief-settings.json"])
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        return {"committed": False, "pushed": False, "message": "No settings changes to publish."}
    _run_git(["commit", "-m", message])
    branch = _run_git(["branch", "--show-current"])
    _run_git(["push", "origin", branch])
    return {"committed": True, "pushed": True, "branch": branch}


def main():
    port = int(os.environ.get("BRIEF_SETTINGS_PORT") or "8766")
    server = ThreadingHTTPServer(("127.0.0.1", port), SettingsHandler)
    print(f"Settings dashboard: http://127.0.0.1:{port}/mockups/brief-format-dashboard.html")
    print(f"Writing settings to: {SETTINGS_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
