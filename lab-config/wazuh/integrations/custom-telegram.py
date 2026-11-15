#!/usr/bin/env python3
"""Integracion custom de Wazuh: reenvia a Telegram las alertas que superan el
<level> del bloque <integration>. Solo stdlib (sirve el Python embebido de Wazuh).
Wazuh lo llama como: custom-telegram <alert_file> <api_key> <hook_url> [<options_file>].
El token va en el hook_url; el chat_id, en <options> o en TELEGRAM_CHAT_ID."""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

LOG_FILE = "/var/ossec/logs/integrations.log"


def debug(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')} custom-telegram: {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, file=sys.stderr)


def load_alert(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def resolve_chat_id(options_file: str | None) -> str | None:
    if options_file and os.path.exists(options_file):
        try:
            with open(options_file) as f:
                return str(json.load(f).get("chat_id") or "") or None
        except Exception as e:
            debug(f"no se pudo leer options_file: {e}")
    return os.environ.get("TELEGRAM_CHAT_ID")


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_message(alert: dict) -> str:
    rule = alert.get("rule", {})
    agent = alert.get("agent", {})
    level = rule.get("level", "?")
    emoji = "\U0001F6A8" if _as_int(level) >= 12 else "⚠️"
    return (
        f"{emoji} <b>Alerta Wazuh - Nivel {level}</b>\n"
        f"<b>Regla:</b> {rule.get('id', '?')} - {rule.get('description', '(sin descripcion)')}\n"
        f"<b>Agente:</b> {agent.get('name', alert.get('manager', {}).get('name', '?'))}\n"
        f"<b>Grupos:</b> {', '.join(rule.get('groups', []))}\n"
        f"<b>Timestamp:</b> {alert.get('timestamp', '')}"
    )


def send_telegram(hook_url: str, chat_id: str, text: str) -> None:
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(hook_url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            debug(f"Telegram respondio {resp.status}: {resp.read()[:200]!r}")


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        debug(f"argumentos insuficientes: {argv}")
        return 1

    alert_file = argv[1]
    hook_url = argv[3]
    options_file = argv[4] if len(argv) > 4 else None

    try:
        alert = load_alert(alert_file)
    except Exception as e:
        debug(f"no se pudo leer la alerta {alert_file}: {e}")
        return 1

    chat_id = resolve_chat_id(options_file)
    if not chat_id:
        debug("falta chat_id (ni en <options> ni en TELEGRAM_CHAT_ID)")
        return 1
    if not hook_url or "api.telegram.org" not in hook_url:
        debug(f"hook_url invalido: {hook_url!r}")
        return 1

    try:
        send_telegram(hook_url, chat_id, build_message(alert))
    except Exception as e:
        debug(f"error enviando a Telegram: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
