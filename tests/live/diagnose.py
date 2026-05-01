"""Diagnostico contra Telegram REAL usando los valores del .env.

Uso:
    .venv/bin/python -m tests.live.diagnose

Comprueba en orden:
  1. getMe → token válido + username del bot.
  2. getWebhookInfo → URL registrada, errores recientes, updates pendientes.
  3. (Opcional) sendMessage al TELEGRAM_CHAT_ID si está configurado, y luego
     deleteMessage para no dejar basura. Solo si --send.

No hace setWebhook (lo hace el lifespan de la app al arrancar).
No es un pytest: es un comando manual que muestra estado real ahora mismo.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from tmjr.config import get_settings


API_BASE = "https://api.telegram.org"


def _mask(token: str) -> str:
    """Muestra el bot_id y los últimos 4 chars del secreto."""
    if ":" not in token:
        return "***"
    bot_id, secret = token.split(":", 1)
    return f"{bot_id}:…{secret[-4:]}"


async def _call(client: httpx.AsyncClient, token: str, method: str, **payload) -> dict:
    r = await client.post(f"{API_BASE}/bot{token}/{method}", json=payload, timeout=10.0)
    r.raise_for_status()
    return r.json()


async def diagnose(send: bool) -> int:
    settings = get_settings()
    token = settings.telegram_token

    if not token:
        print("✗ TELEGRAM_TOKEN no está configurado en .env")
        return 1

    print(f"→ Token: {_mask(token)}")
    print(f"→ Webhook URL configurada: {settings.telegram_webhook_url or '(vacía)'}")
    print(f"→ Chat ID configurado: {settings.telegram_chat_id or '(vacío)'}")
    print()

    async with httpx.AsyncClient() as client:
        # 1. getMe
        try:
            me = await _call(client, token, "getMe")
        except httpx.HTTPStatusError as e:
            print(f"✗ getMe falló: HTTP {e.response.status_code} {e.response.text}")
            return 2
        if not me.get("ok"):
            print(f"✗ getMe devolvió ok=False: {me}")
            return 2
        bot = me["result"]
        print(f"✓ getMe OK")
        print(f"   bot_id   = {bot['id']}")
        print(f"   username = @{bot['username']}")
        print(f"   name     = {bot['first_name']}")
        print()

        # 2. getWebhookInfo
        try:
            info = await _call(client, token, "getWebhookInfo")
        except httpx.HTTPStatusError as e:
            print(f"✗ getWebhookInfo falló: {e.response.text}")
            return 3
        result = info["result"]
        print("→ getWebhookInfo:")
        for k in ("url", "has_custom_certificate", "pending_update_count",
                  "last_error_date", "last_error_message", "max_connections",
                  "ip_address"):
            if k in result and result[k] not in (None, "", 0, False):
                print(f"   {k:30s} = {result[k]}")

        registered_url = result.get("url", "")
        if not registered_url:
            print("⚠ Webhook NO registrado todavía. Arranca la app (lifespan llama setWebhook).")
        elif registered_url != settings.telegram_webhook_url:
            print(f"⚠ Webhook registrado != el del .env:")
            print(f"   .env  : {settings.telegram_webhook_url}")
            print(f"   Telegram: {registered_url}")
        else:
            print("✓ URL del webhook coincide con .env")

        if result.get("last_error_message"):
            print(f"⚠ ÚLTIMO ERROR de Telegram al entregar updates: "
                  f"{result['last_error_message']}")
        print()

        # 3. sendMessage (opcional)
        if send:
            chat_id = settings.telegram_chat_id
            if not chat_id:
                print("⚠ --send pedido pero TELEGRAM_CHAT_ID está vacío. Skip.")
                return 0

            try:
                sent = await _call(
                    client, token, "sendMessage",
                    chat_id=chat_id,
                    text="🔧 smoke desde tests/live/diagnose — borrando en 1s",
                )
            except httpx.HTTPStatusError as e:
                print(f"✗ sendMessage falló: HTTP {e.response.status_code} {e.response.text}")
                return 4

            if not sent.get("ok"):
                print(f"✗ sendMessage devolvió ok=False: {sent}")
                return 4
            msg_id = sent["result"]["message_id"]
            print(f"✓ sendMessage OK al chat {chat_id} (message_id={msg_id})")

            # Borra para no ensuciar
            await asyncio.sleep(1)
            try:
                await _call(client, token, "deleteMessage",
                            chat_id=chat_id, message_id=msg_id)
                print(f"✓ deleteMessage OK")
            except httpx.HTTPStatusError as e:
                print(f"⚠ No pude borrar el mensaje (no crítico): {e.response.text}")

    print()
    print("─── Diagnóstico completo ───")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Diagnostico live contra Telegram")
    p.add_argument(
        "--send", action="store_true",
        help="Hace sendMessage de prueba al TELEGRAM_CHAT_ID y lo borra después.",
    )
    args = p.parse_args()
    return asyncio.run(diagnose(send=args.send))


if __name__ == "__main__":
    sys.exit(main())
