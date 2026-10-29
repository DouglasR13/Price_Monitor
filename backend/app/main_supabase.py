"""
PriceRadar AI — FastAPI main entry point (Supabase backend).
Identical interface to main.py but uses Supabase (PostgreSQL) instead of SQLite.
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import logging

from app.config import BASE_DIR, HOST, PORT
from app.database_supabase import get_supabase, get_setting, set_setting
from app.models_repo_supabase import ProductRepo, UserRepo
from app.schemas import (
    ProductCreate, ProductUpdate, SearchPreviewRequest,
    TelegramSettings, TelegramTestRequest, UserLogin, UserRegister,
)
from app.scraper import fetch_buscape_offers
from app.analyzer import analyze_price_opportunity_supabase
from app.telegram_bot import send_product_report, send_telegram_message, test_telegram_connection
from app.email_service import send_daily_email_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("price-monitor-supabase")

app = FastAPI(
    title="PriceRadar AI — Supabase Backend",
    description="Motor de busca de preços com banco de dados Supabase (PostgreSQL)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = BASE_DIR / "frontend"


@app.on_event("startup")
def on_startup():
    try:
        sb = get_supabase()
        # Quick connectivity check
        sb.table("users").select("id").limit(1).execute()
        logger.info("✅ Supabase conectado com sucesso!")
        _seed_supabase_if_empty()
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao Supabase: {e}")
        raise


def _seed_supabase_if_empty():
    """Creates default admin and demo user in Supabase if they don't exist yet."""
    repo = UserRepo()
    if not repo.get_by_email("admin@radar.com"):
        repo.create(
            name="Administrador",
            email="admin@radar.com",
            password="Admin@123",
            role="admin",
        )
        logger.info("Usuário admin criado no Supabase.")
    if not repo.get_by_email("usuario@demo.com"):
        repo.create(
            name="Carlos Silva",
            email="usuario@demo.com",
            password="User@123",
            role="user",
        )
        logger.info("Usuário demo criado no Supabase.")


# ==================== AUTHENTICATION & USER ENDPOINTS ====================

@app.post("/api/auth/login")
def login(payload: UserLogin):
    repo = UserRepo()
    res = repo.authenticate(payload.email, payload.password)
    if not res.get("success"):
        status_code = 429 if res.get("error") == "LOCKED" else 401
        raise HTTPException(status_code=status_code, detail=res)
    return res


@app.post("/api/auth/register")
def register(payload: UserRegister):
    repo = UserRepo()
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado no sistema.")
    try:
        user_id = repo.create(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role="user",
            telegram_chat_id=payload.telegram_chat_id or "",
            notification_hour=22,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"success": True, "user": repo.get_by_id(user_id)}


@app.get("/api/auth/users")
def list_users():
    return UserRepo().list_all()


@app.post("/api/email/test-daily-report")
def test_daily_email(user_id: int):
    u_repo = UserRepo()
    p_repo = ProductRepo()
    user = u_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    products = p_repo.get_all(user_id=user_id, role="user")
    return send_daily_email_report(
        to_email=user["email"],
        user_name=user["name"],
        products=products,
    )


# ==================== PRODUCT ENDPOINTS ====================

@app.get("/api/products")
def list_products(user_id: Optional[int] = None, role: str = "admin", active_only: bool = False):
    return ProductRepo().get_all(user_id=user_id, role=role, active_only=active_only)


@app.post("/api/products")
def create_product(payload: ProductCreate, user_id: Optional[int] = None):
    repo = ProductRepo()
    product_id = repo.create(payload, user_id=user_id)

    # Trigger first price check immediately
    try:
        check_single_product(product_id, send_telegram=False)
    except Exception as e:
        logger.warning(f"Initial scrape error for product {product_id}: {e}")

    return repo.get_by_id(product_id)


@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    prod = ProductRepo().get_by_id(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return prod


@app.put("/api/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdate):
    repo = ProductRepo()
    updated = repo.update(product_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return repo.get_by_id(product_id)


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    success = ProductRepo().delete(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return {"success": True, "message": "Produto removido com sucesso."}


# ==================== PRICE CHECK & SCRAPING ====================

def check_single_product(product_id: int, send_telegram: bool = True) -> Dict[str, Any]:
    repo = ProductRepo()
    product = repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Retrieve user's ignored stores
    user_id = product.get("user_id")
    ignored = repo.get_ignored_stores(user_id) if user_id else []

    search_q = product["search_query"] or f"{product['brand']} {product['name']}"
    scraped = fetch_buscape_offers(
        query=search_q,
        brand=product.get("brand", ""),
        ignored_stores=ignored
    )

    # Get history for analysis
    history = repo.get_history(product_id, limit=30)

    analysis = analyze_price_opportunity_supabase(
        history=history,
        current_min_price=scraped["min_price"],
        current_avg_price=scraped["avg_price"],
        target_price=product.get("target_price"),
    )

    # Update product image if empty
    if not product.get("image_url") and scraped.get("image_url"):
        from app.database_supabase import get_supabase as _sb
        _sb().table("products").update({"image_url": scraped["image_url"]}).eq("id", product_id).execute()

    record_id = repo.add_price_record(
        product_id=product_id,
        scraped=scraped,
        analysis=analysis,
    )
    record = repo.get_record_by_id(record_id)

    telegram_result = None
    if send_telegram:
        try:
            telegram_result = send_product_report(product, record)
        except Exception as ex:
            logger.error(f"Erro Telegram: {ex}")

    return {
        "product_id": product_id,
        "product_name": product["name"],
        "record": record,
        "telegram_notification": telegram_result,
    }


# ==================== IGNORED STORES ENDPOINTS ====================

@app.get("/api/user/ignored-stores")
def get_user_ignored_stores(user_id: int):
    repo = ProductRepo()
    return {"user_id": user_id, "ignored_stores": repo.get_ignored_stores(user_id)}


@app.post("/api/user/ignore-store")
def ignore_store(payload: Dict[str, Any]):
    user_id = payload.get("user_id")
    store_name = payload.get("store_name", "").strip()
    product_id = payload.get("product_id")

    if not user_id or not store_name:
        raise HTTPException(status_code=400, detail="user_id e store_name são obrigatórios.")

    repo = ProductRepo()
    updated_stores = repo.add_ignored_store(user_id, store_name)

    # If product_id was provided, recheck immediately to recalculate prices without this store
    new_product_data = None
    if product_id:
        try:
            check_single_product(product_id, send_telegram=False)
            new_product_data = repo.get_by_id(product_id)
        except Exception as e:
            logger.warning(f"Error re-checking product {product_id} after ignoring store: {e}")

    return {
        "success": True,
        "message": f"A loja '{store_name}' foi adicionada à sua lista de ignoradas.",
        "ignored_stores": updated_stores,
        "updated_product": new_product_data
    }


@app.post("/api/user/unignore-store")
def unignore_store(payload: Dict[str, Any]):
    user_id = payload.get("user_id")
    store_name = payload.get("store_name", "").strip()

    if not user_id or not store_name:
        raise HTTPException(status_code=400, detail="user_id e store_name são obrigatórios.")

    repo = ProductRepo()
    updated_stores = repo.remove_ignored_store(user_id, store_name)

    return {
        "success": True,
        "message": f"A loja '{store_name}' foi reativada.",
        "ignored_stores": updated_stores
    }


# ==================== DAILY CRON AT 22:00 ====================

@app.get("/api/cron/daily-report")
@app.post("/api/cron/daily-report")
def run_daily_cron_routine(background_tasks: BackgroundTasks):
    """
    Called by cloud cron (e.g. cron-job.org or Render Cron) at 22:00.
    1. Scrapes all active products with each user's store preferences.
    2. Sends email reports to all registered users.
    """
    logger.info("⏰ Iniciando rotina automática diária das 22:00...")
    u_repo = UserRepo()
    p_repo = ProductRepo()

    users = u_repo.list_all()
    cron_results = []

    for u in users:
        u_id = u["id"]
        # Check products owned by this user
        user_products = p_repo.get_all(user_id=u_id, role=u["role"], active_only=True)
        if not user_products:
            continue

        # Re-check prices for all products of this user
        for prod in user_products:
            try:
                check_single_product(prod["id"], send_telegram=False)
            except Exception as e:
                logger.warning(f"Erro atualizando produto {prod['id']}: {e}")

        # Fetch freshly updated product data
        fresh_products = p_repo.get_all(user_id=u_id, role=u["role"], active_only=True)

        # Dispatch email report
        try:
            email_res = send_daily_email_report(
                to_email=u["email"],
                user_name=u["name"],
                products=fresh_products
            )
            cron_results.append({
                "user_id": u_id,
                "email": u["email"],
                "status": "SENT" if email_res.get("success") else "FAILED",
                "detail": email_res
            })
        except Exception as ex:
            cron_results.append({
                "user_id": u_id,
                "email": u["email"],
                "status": "ERROR",
                "error": str(ex)
            })

    return {
        "timestamp": datetime.now().isoformat(),
        "routine": "daily_22_00",
        "users_processed": len(cron_results),
        "results": cron_results
    }


@app.post("/api/products/{product_id}/check")
def manual_check_product(product_id: int, notify_telegram: bool = False):
    return check_single_product(product_id, send_telegram=notify_telegram)


@app.post("/api/check-all")
def check_all_products(notify_telegram: bool = True):
    """Used by n8n daily cron schedule."""
    products = ProductRepo().get_all(active_only=True)
    results = []
    for prod in products:
        try:
            res = check_single_product(prod["id"], send_telegram=notify_telegram)
            results.append(res)
        except Exception as e:
            logger.error(f"Erro checando produto {prod['id']}: {e}")
            results.append({"product_id": prod["id"], "product_name": prod["name"], "error": str(e)})

    return {
        "timestamp": datetime.now().isoformat(),
        "total_checked": len(products),
        "results": results,
    }


@app.get("/api/products/{product_id}/history")
def get_product_history(product_id: int, limit: int = 30):
    return ProductRepo().get_history(product_id, limit=limit)


@app.post("/api/search-preview")
def preview_search(payload: SearchPreviewRequest):
    q = payload.query.strip()
    if payload.brand:
        q = f"{payload.brand} {q}"
    return fetch_buscape_offers(q)


# ==================== DASHBOARD STATS ====================

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    return ProductRepo().get_dashboard_stats()


# ==================== SETTINGS ====================

@app.get("/api/settings")
def get_settings():
    token = get_setting("telegram_bot_token", "")
    chat_id = get_setting("telegram_chat_id", "")
    masked_token = (token[:6] + "..." + token[-4:]) if len(token) > 10 else ("Configurado" if token else "")
    return {
        "telegram_bot_token": masked_token,
        "telegram_chat_id": chat_id,
        "is_configured": bool(token and chat_id),
    }


@app.post("/api/settings")
def save_settings(payload: Dict[str, str]):
    if "telegram_bot_token" in payload and payload["telegram_bot_token"].strip():
        if "..." not in payload["telegram_bot_token"]:
            set_setting("telegram_bot_token", payload["telegram_bot_token"].strip())
    if "telegram_chat_id" in payload:
        set_setting("telegram_chat_id", payload["telegram_chat_id"].strip())
    return {"success": True, "message": "Configurações salvas com sucesso!"}


@app.post("/api/telegram/test")
def test_telegram(payload: TelegramTestRequest):
    token = payload.bot_token or get_setting("telegram_bot_token")
    chat_id = payload.chat_id or get_setting("telegram_chat_id")
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Token do bot ou Chat ID não preenchidos.")

    text = (
        "🤖 <b>PriceRadar AI — Conexão Bem-Sucedida!</b>\n\n"
        "✅ Bot conectado com sucesso ao sistema de monitoramento.\n"
        "📅 Você receberá relatórios diários de preços e alertas de desconto aqui!"
    )
    res = send_telegram_message(text=text, bot_token=token, chat_id=chat_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Falha ao enviar mensagem"))

    if payload.bot_token:
        set_setting("telegram_bot_token", payload.bot_token.strip())
    if payload.chat_id:
        set_setting("telegram_chat_id", payload.chat_id.strip())

    return {"success": True, "message": "Mensagem de teste enviada com sucesso!"}


@app.get("/api/n8n/export-workflow")
def export_n8n_workflow():
    workflow_path = BASE_DIR / "n8n" / "workflows" / "daily-price-monitor.json"
    if workflow_path.exists():
        with open(workflow_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "Workflow file not found"}


# ==================== STATIC FRONTEND SERVING ====================

if frontend_dir.exists():
    app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
    app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")
    if (frontend_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")


@app.get("/")
def serve_index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "PriceRadar AI (Supabase) is running."}
