from typing import Dict, Any, List, Optional
import sqlite3


def _evaluate_prices(
    records: List[Dict[str, Any]],
    current_min_price: float,
    current_avg_price: float,
    target_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Core price evaluation logic shared by both SQLite and Supabase paths."""
    if not records:
        reason = "Primeiro registro de monitoramento. Base histórica iniciada hoje."
        rec = "NORMAL"
        if target_price and current_min_price <= target_price:
            rec = "EXCELLENT"
            reason = f"🎯 Preço atual (R$ {current_min_price:.2f}) já está abaixo do seu preço-alvo (R$ {target_price:.2f})!"
        return {"recommendation": rec, "recommendation_reason": reason, "delta_pct": 0.0, "delta_amount": 0.0}

    yesterday_min = records[0]["min_price"]
    delta_amount = round(current_min_price - yesterday_min, 2)
    delta_pct = round(((current_min_price - yesterday_min) / yesterday_min) * 100, 2) if yesterday_min > 0 else 0.0

    all_prices = [r["min_price"] for r in records]
    all_time_min = min(all_prices)
    moving_avg_7d = sum(r["min_price"] for r in records[:7]) / len(records[:7])

    recommendation = "NORMAL"
    reason = "Preço estável, oscilando dentro da faixa média do mercado."

    if target_price and current_min_price <= target_price:
        recommendation = "EXCELLENT"
        diff = target_price - current_min_price
        reason = f"🎯 Atingiu a meta! Preço R$ {current_min_price:.2f} está R$ {diff:.2f} abaixo do alvo de R$ {target_price:.2f}."
    elif current_min_price <= all_time_min:
        recommendation = "EXCELLENT"
        reason = f"🔥 Menor Preço Histórico! Novo recorde de baixa (R$ {current_min_price:.2f})."
    elif current_min_price <= all_time_min * 1.025:
        recommendation = "EXCELLENT"
        reason = f"🟢 Excelente! Preço colado na mínima histórica (a R$ {current_min_price - all_time_min:.2f} do recorde)."
    elif current_min_price <= moving_avg_7d * 0.93:
        discount = round(((moving_avg_7d - current_min_price) / moving_avg_7d) * 100, 1)
        recommendation = "EXCELLENT"
        reason = f"📉 Queda brusca de {discount}% em relação à média dos últimos dias! Ótima oportunidade."
    elif current_min_price >= moving_avg_7d * 1.05:
        inflation = round(((current_min_price - moving_avg_7d) / moving_avg_7d) * 100, 1)
        recommendation = "HIGH"
        reason = f"⏳ Preço em alta (+{inflation}% acima da média semanal). Recomendamos aguardar."
    elif delta_pct < -3.0:
        reason = f"Tendência de queda (-{abs(delta_pct)}% hoje). Vale acompanhar nas próximas horas."

    return {"recommendation": recommendation, "recommendation_reason": reason, "delta_pct": delta_pct, "delta_amount": delta_amount}


def analyze_price_opportunity_supabase(
    history: List[Dict[str, Any]],
    current_min_price: float,
    current_avg_price: float,
    target_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Supabase-compatible version — accepts pre-fetched history list."""
    # history is already ordered by checked_at ASC from get_history(); reverse for newest-first
    records = list(reversed(history))
    return _evaluate_prices(records, current_min_price, current_avg_price, target_price)


def analyze_price_opportunity(
    conn: sqlite3.Connection,
    product_id: int,
    current_min_price: float,
    current_avg_price: float,
    target_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyzes current price against historical data to evaluate whether today is the best day to buy.
    Returns recommendation status ('EXCELLENT', 'NORMAL', 'HIGH'), reason, delta_pct, delta_amount.
    """
    # Fetch historical records for this product
    cursor = conn.cursor()
    records = cursor.execute("""
        SELECT min_price, avg_price, checked_at 
        FROM price_records 
        WHERE product_id = ? 
        ORDER BY checked_at DESC
    """, (product_id,)).fetchall()

    if not records:
        # First record ever for this product
        reason = "Primeiro registro de monitoramento. Base histórica iniciada hoje."
        rec = "NORMAL"
        if target_price and current_min_price <= target_price:
            rec = "EXCELLENT"
            reason = f"🎯 Preço atual (R$ {current_min_price:.2f}) já está abaixo do seu preço-alvo (R$ {target_price:.2f})!"
        return {
            "recommendation": rec,
            "recommendation_reason": reason,
            "delta_pct": 0.0,
            "delta_amount": 0.0
        }

    # Historical stats
    yesterday_min = records[0]["min_price"]
    delta_amount = round(current_min_price - yesterday_min, 2)
    delta_pct = round(((current_min_price - yesterday_min) / yesterday_min) * 100, 2) if yesterday_min > 0 else 0.0

    all_prices = [r["min_price"] for r in records]
    all_time_min = min(all_prices)
    all_time_max = max(all_prices)

    # 7-day moving average
    recent_records = records[:7]
    moving_avg_7d = sum(r["min_price"] for r in recent_records) / len(recent_records)

    # Evaluation Rules
    recommendation = "NORMAL"
    reason = "Preço estável, oscilando dentro da faixa média do mercado."

    # Condition 1: Below Target Price
    if target_price and current_min_price <= target_price:
        recommendation = "EXCELLENT"
        diff = target_price - current_min_price
        reason = f"🎯 Atingiu a meta! Preço R$ {current_min_price:.2f} está R$ {diff:.2f} abaixo do seu alvo de R$ {target_price:.2f}."

    # Condition 2: Historical All-Time Low (or within 2%)
    elif current_min_price <= all_time_min:
        recommendation = "EXCELLENT"
        reason = f"🔥 Menor Preço Histórico! Novo recorde de baixa desde o início do rastreio (R$ {current_min_price:.2f})."
    elif current_min_price <= all_time_min * 1.025:
        recommendation = "EXCELLENT"
        reason = f"🟢 Excelente momento! Preço está colado na mínima histórica (a apenas R$ {current_min_price - all_time_min:.2f} do recorde)."

    # Condition 3: Significant drop vs 7-day moving average (>= 7% drop)
    elif current_min_price <= moving_avg_7d * 0.93:
        discount = round(((moving_avg_7d - current_min_price) / moving_avg_7d) * 100, 1)
        recommendation = "EXCELLENT"
        reason = f"📉 Queda brusca de {discount}% em relação à média dos últimos dias! Ótima oportunidade."

    # Condition 4: High price (> 5% above moving average)
    elif current_min_price >= moving_avg_7d * 1.05:
        recommendation = "HIGH"
        inflation = round(((current_min_price - moving_avg_7d) / moving_avg_7d) * 100, 1)
        reason = f"⏳ Preço em alta (+{inflation}% acima da média semanal). Recomendamos aguardar antes de comprar."

    elif delta_pct < -3.0:
        recommendation = "NORMAL"
        reason = f"Tendência de queda (-{abs(delta_pct)}% hoje). Vale a pena ficar de olho nas próximas horas."

    return {
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "delta_pct": delta_pct,
        "delta_amount": delta_amount
    }
