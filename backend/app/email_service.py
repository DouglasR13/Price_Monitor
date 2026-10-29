import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# SMTP configuration from environment or settings
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "PriceRadar AI <alertas@priceradar.local>")

def build_email_offers_snippet(offers: List[Dict[str, Any]], fallback_url: str) -> str:
    """Renders a compact table of tracked stores and prices inside the email."""
    if not offers:
        return ""
    rows = ""
    for o in offers[:5]:
        is_best_badge = '<span style="background: #10b981; color: #ffffff; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 5px; font-weight: bold;">MELHOR PREÇO</span>' if o.get("is_best") else ""
        is_official_badge = '<span style="background: #6366f1; color: #ffffff; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 5px; font-weight: bold;">LOJA OFICIAL</span>' if o.get("is_official") else ""
        store_link = o.get("url") or fallback_url
        rows += f"""
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);">
          <td style="padding: 7px 4px; font-size: 12px; color: #cbd5e1;">
            <strong>{o['store_name']}</strong> {is_best_badge} {is_official_badge}
          </td>
          <td align="right" style="padding: 7px 4px; font-size: 13px; color: #38bdf8; font-weight: bold; font-family: monospace;">
            R$ {o['price']:,.2f}
          </td>
          <td align="right" style="padding: 7px 0 7px 8px;">
            <a href="{store_link}" target="_blank" style="color: #818cf8; font-size: 11px; text-decoration: none; font-weight: bold;">Ver ↗</a>
          </td>
        </tr>
        """
    return f"""
    <div style="background: rgba(15, 23, 42, 0.7); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.05);">
      <div style="font-size: 11px; font-weight: bold; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Comparativo de Lojas:</div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        {rows}
      </table>
    </div>
    """

def build_daily_email_html(user_name: str, products: List[Dict[str, Any]]) -> str:
    """Generates a responsive modern HTML email report for the user's products."""
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")

    product_cards_html = ""
    for p in products:
        rec = p.get("latest_record") or {}
        min_p = rec.get("min_price", 0)
        avg_p = rec.get("avg_price", 0)
        store = rec.get("best_store", "Loja Online")
        delta = rec.get("delta_pct", 0)
        recommendation = rec.get("recommendation", "NORMAL")
        reason = rec.get("recommendation_reason", "")
        best_url = rec.get("best_url", "#")
        img = p.get("image_url") or "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300"

        # Badge colors
        if recommendation == "EXCELLENT":
            badge_color = "#10b981"
            badge_text = "🟢 EXCELENTE MOMENTO DE COMPRA"
        elif recommendation == "HIGH":
            badge_color = "#ef4444"
            badge_text = "🔴 PREÇO EM ALTA — AGUARDAR"
        else:
            badge_color = "#f59e0b"
            badge_text = "🟡 PREÇO REGULAR"

        delta_str = f"{delta:+.1f}% vs ontem" if delta != 0 else "0.0% estável"

        product_cards_html += f"""
        <div style="background-color: #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.08);">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="80" valign="top">
                <img src="{img}" alt="{p['name']}" width="75" height="75" style="border-radius: 8px; object-fit: cover; background: #0f172a;" />
              </td>
              <td style="padding-left: 16px;" valign="top">
                <span style="font-size: 11px; text-transform: uppercase; color: #818cf8; font-weight: bold;">{p['brand']} • {p['category']}</span>
                <h3 style="margin: 4px 0 8px 0; font-size: 16px; color: #ffffff; font-family: sans-serif;">{p['name']}</h3>
                
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 10px;">
                  <tr>
                    <td>
                      <span style="font-size: 12px; color: #94a3b8;">Menor Preço Hoje:</span><br />
                      <strong style="font-size: 20px; color: #38bdf8; font-family: monospace;">R$ {min_p:,.2f}</strong>
                      <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.1); color: #cbd5e1; margin-left: 6px;">{delta_str}</span>
                    </td>
                    <td align="right" valign="bottom">
                      <span style="font-size: 12px; color: #94a3b8;">Loja: <strong>{store}</strong></span><br />
                      <span style="font-size: 11px; color: #64748b;">Média: R$ {avg_p:,.2f}</span>
                    </td>
                  </tr>
                </table>

                <div style="background: rgba(0,0,0,0.3); border-left: 4px solid {badge_color}; padding: 8px 12px; border-radius: 4px; margin-bottom: 12px;">
                  <strong style="font-size: 12px; color: {badge_color};">{badge_text}</strong><br />
                  <span style="font-size: 12px; color: #cbd5e1;">{reason}</span>
                </div>

                <!-- Stores comparison list -->
                {build_email_offers_snippet(rec.get("offers", []), best_url)}

                <div style="margin-top: 12px;">
                  <a href="{best_url}" target="_blank" style="display: inline-block; background-color: #10b981; color: #ffffff; font-weight: bold; font-size: 13px; text-decoration: none; padding: 8px 16px; border-radius: 6px;">
                    🛒 Comprar na {store}
                  </a>
                </div>
              </td>
            </tr>
          </table>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>Relatório Diário de Preços — PriceRadar</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f8fafc;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #0b0f19; padding: 24px 0;">
        <tr>
          <td align="center">
            <table width="620" cellpadding="0" cellspacing="0" border="0" style="background-color: #0f172a; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden; padding: 28px;">
              <!-- Header -->
              <tr>
                <td>
                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
                    <span style="font-size: 24px;">📊</span>
                    <strong style="font-size: 20px; color: #ffffff;">PriceRadar AI</strong>
                    <span style="font-size: 12px; background: rgba(99,102,241,0.2); color: #a5b4fc; padding: 3px 8px; border-radius: 12px; margin-left: 8px;">Relatório das 22:00</span>
                  </div>
                  <h2 style="margin: 0 0 6px 0; font-size: 22px; color: #ffffff;">Boa noite, {user_name}!</h2>
                  <p style="margin: 0 0 20px 0; font-size: 14px; color: #94a3b8; line-height: 1.5;">
                    Aqui está o levantamento diário dos seus produtos monitorados atualizado hoje, <strong>{now_str}</strong>. Confira se hoje é o momento ideal de compra:
                  </p>
                </td>
              </tr>

              <!-- Products List -->
              <tr>
                <td>
                  {product_cards_html}
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 18px; margin-top: 12px; text-align: center; color: #64748b; font-size: 12px;">
                  Você está recebendo este e-mail porque configurou alertas de preço no <strong>PriceRadar AI</strong>.<br />
                  Horário padrão programado: <strong>22:00</strong>. Acesse o seu painel web para alterar suas preferências.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    return html

def send_daily_email_report(
    to_email: str,
    user_name: str,
    products: List[Dict[str, Any]],
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends the 22:00 daily HTML email report.
    If SMTP server is not configured, saves a simulated delivery with full HTML preview.
    """
    host = smtp_host or SMTP_HOST
    port = smtp_port or SMTP_PORT
    user = smtp_user or SMTP_USER
    pwd = smtp_password or SMTP_PASSWORD

    subject = f"📊 PriceRadar — Relatório de Preços das 22:00 ({len(products)} produtos)"
    html_content = build_daily_email_html(user_name, products)

    # If SMTP is configured, send real email
    if host and user and pwd:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(host, port, timeout=12) as server:
                server.starttls()
                server.login(user, pwd)
                server.sendmail(SMTP_FROM, [to_email], msg.as_string())

            logger.info(f"Relatório de e-mail enviado com sucesso para {to_email}")
            return {"success": True, "mode": "SMTP_SENT", "recipient": to_email}
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail via SMTP: {e}")
            return {"success": False, "error": str(e)}

    # Otherwise, simulated mode (logs delivery and returns preview)
    logger.info(f"[SIMULAÇÃO] E-mail das 22:00 gerado com sucesso para {to_email} ({len(products)} produtos).")
    return {
        "success": True,
        "mode": "SIMULATED",
        "recipient": to_email,
        "subject": subject,
        "products_count": len(products),
        "message": f"E-mail das 22:00 gerado para {to_email}. Para envio real na sua caixa de entrada, configure suas credenciais SMTP no .env."
    }
