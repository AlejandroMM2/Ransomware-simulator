#!/usr/bin/env python3
"""
custom-telegram.py — Integracion custom de Wazuh para reenviar alertas a Telegram.

Wazuh (manager) invoca este script cuando una alerta supera el <level> configurado
en el bloque <integration> de ossec.conf. Contrato de argumentos de Wazuh:

    custom-telegram <alert_file> <api_key> <hook_url> [<options_file>]

  argv[1] = ruta al fichero JSON con la alerta que ha disparado la integracion
  argv[2] = api_key          (campo <api_key> de ossec.conf; vacio si no se usa)
  argv[3] = hook_url         (campo <hook_url>: URL sendMessage del bot de Telegram)
  argv[4] = options_file     (opcional; JSON del campo <options>, p.ej. {"chat_id": "..."})

No requiere dependencias externas: usa solo la biblioteca estandar (urllib), de modo
que funciona con el interprete Python embebido de Wazuh sin instalar nada.

El chat_id se obtiene, por este orden, de: el fichero de opciones (argv[4]),
la variable de entorno TELEGRAM_CHAT_ID. El token del bot va embebido en el hook_url.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

LOG_FILE = "/var/ossec/logs/integrations.log"


def debug(msg: str) -> None:
    """Registra en el log de integraciones de Wazuh (best-effort)."""
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
                opts = json.load(f)
            cid = opts.get("chat_id")
            if cid:
                return str(cid)
        except Exception as e:
            debug(f"no se pudo leer options_file: {e}")
    return os.environ.get("TELEGRAM_CHAT_ID")


def build_message(alert: dict) -> str:
    """Compone un mensaje legible a partir de los campos relevantes de la alerta."""
    rule = alert.get("rule", {})
    agent = alert.get("agent", {})
    level = rule.get("level", "?")
    rule_id = rule.get("id", "?")
    desc = rule.get("description", "(sin descripcion)")
    groups = ", ".join(rule.get("groups", []))
    agent_name = agent.get("name", alert.get("manager", {}).get("name", "?"))
    ts = alert.get("timestamp", "")

    emoji = "\U0001F6A8" if _as_int(level) >= 12 else "⚠️"
    return (
        f"{emoji} <b>Alerta Wazuh - Nivel {level}</b>\n"
        f"<b>Regla:</b> {rule_id} - {desc}\n"
        f"<b>Agente:</b> {agent_name}\n"
        f"<b>Grupos:</b> {groups}\n"
        f"<b>Timestamp:</b> {ts}"
    )


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
