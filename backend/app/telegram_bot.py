import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.database import get_setting

logger = logging.getLogger(__name__)

def get_telegram_creds(override_token: Optional[str] = None, override_chat: Optional[str] = None):
    token = override_token or get_setting("telegram_bot_token") or TELEGRAM_BOT_TOKEN
    chat_id = override_chat or get_setting("telegram_chat_id") or TELEGRAM_CHAT_ID
    return token.strip(), chat_id.strip()

def send_telegram_message(
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None
) -> Dict[str, Any]:
    """Sends an HTML formatted message to Telegram."""
    token, target_chat = get_telegram_creds(bot_token, chat_id)
    if not token or not target_chat:
        return {"success": False, "error": "Token do bot ou Chat ID não configurados."}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("ok"):
            return {"success": True, "message_id": data["result"]["message_id"]}
        else:
            return {"success": False, "error": data.get("description", "Erro desconhecido Telegram")}
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem Telegram: {e}")
        return {"success": False, "error": str(e)}

def format_daily_report_html(
    product_name: str,
    brand: str,
    min_price: float,
    max_price: float,
    avg_price: float,
    best_store: str,
    best_url: str,
    recommendation: str,
    recommendation_reason: str,
    delta_pct: float,
    target_price: Optional[float] = None
) -> str:
    """Formats a beautiful HTML Telegram report for a single monitored product."""
    
    # Delta indicator
    if delta_pct < -0.01:
        delta_str = f"📉 <b>{delta_pct:.1f}%</b> (Caiu vs ontem!)"
    elif delta_pct > 0.01:
        delta_str = f"📈 <b>+{delta_pct:.1f}%</b> (Subiu vs ontem)"
    else:
        delta_str = "➡️ <b>0.0%</b> (Estável)"

    # Verdict Badge
    if recommendation == "EXCELLENT":
        badge = "🟢 <b>EXCELENTE MOMENTO DE COMPRA!</b>"
    elif recommendation == "HIGH":
        badge = "🔴 <b>PREÇO ALTO — RECOMENDAMOS AGUARDAR</b>"
    else:
        badge = "🟡 <b>PREÇO ESTÁVEL / REGULAR</b>"

    target_str = ""
    if target_price:
        target_str = f"🎯 <b>Seu Alvo de Preço:</b> R$ {target_price:,.2f}\n".replace(',', 'X').replace('.', ',').replace('X', '.')

    min_fmt = f"R$ {min_price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    avg_fmt = f"R$ {avg_price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    max_fmt = f"R$ {max_price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html = (
        f"📊 <b>RELATÓRIO DIÁRIO DE PREÇOS</b>\n"
        f"🕒 <i>{now_str}</i>\n\n"
        f"📦 <b>Produto:</b> {product_name} ({brand})\n"
        f"{target_str}\n"
        f"💰 <b>Menor Preço Hoje:</b> {min_fmt}\n"
        f"🏪 <b>Loja Mais Barata:</b> <b>{best_store}</b>\n"
        f"📊 <b>Preço Médio do Mercado:</b> {avg_fmt}\n"
        f"📈 <b>Maior Preço Encontrado:</b> {max_fmt}\n"
        f"🔄 <b>Variação:</b> {delta_str}\n\n"
        f"💡 <b>Veredito do Dia:</b>\n"
        f"{badge}\n"
        f"<i>{recommendation_reason}</i>\n"
    )

    if best_url:
        html += f"\n🔗 <a href='{best_url}'>Acessar Melhor Oferta ({best_store})</a>"

    return html

def send_product_report(product: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to assemble and send a product price report to Telegram."""
    text = format_daily_report_html(
        product_name=product["name"],
        brand=product["brand"],
        min_price=record["min_price"],
        max_price=record["max_price"],
        avg_price=record["avg_price"],
        best_store=record["best_store"],
        best_url=record["best_url"] or "",
        recommendation=record["recommendation"],
        recommendation_reason=record.get("recommendation_reason", ""),
        delta_pct=record.get("delta_pct", 0.0),
        target_price=product.get("target_price")
    )

    reply_markup = None
    if record.get("best_url"):
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": f"🛒 Ver Oferta na {record['best_store']}", "url": record["best_url"]}
                ]
            ]
        }

    return send_telegram_message(text=text, reply_markup=reply_markup)

def test_telegram_connection(bot_token: str, chat_id: str) -> Dict[str, Any]:
    """Sends a verification ping to Telegram to validate credentials."""
    text = (
        "🤖 <b>Monitor de Preços — Conexão Verificada!</b>\n\n"
        "✅ O seu bot do Telegram foi conectado com sucesso!\n"
        "📈 A partir de agora, os relatórios diários de preços e oportunidades de compra serão entregues aqui."
    )
    return send_telegram_message(text=text, bot_token=bot_token, chat_id=chat_id)
