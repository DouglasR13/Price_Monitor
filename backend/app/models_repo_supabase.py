"""
Supabase-backed repositories for User and Product data.
Drop-in replacement for models_repo.py — same interface, different backend.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from app.schemas import ProductCreate, ProductUpdate
from app.auth_utils import (
    validate_password_strength,
    check_account_lockout,
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
)
from app.database_supabase import get_supabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


def _row_to_public_user(row: dict) -> dict:
    """Strips sensitive fields before returning to client."""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "telegram_chat_id": row.get("telegram_chat_id", ""),
        "notification_hour": row.get("notification_hour", 22),
        "email_notifications_enabled": row.get("email_notifications_enabled", True),
        "created_at": row.get("created_at", ""),
    }


# ---------------------------------------------------------------------------
# UserRepo (Supabase)
# ---------------------------------------------------------------------------

class UserRepo:
    def __init__(self):
        self.sb = get_supabase()

    @staticmethod
    def hash_password(password: str) -> str:
        return _hash_password(password)

    def create(
        self,
        name: str,
        email: str,
        password: str,
        role: str = "user",
        telegram_chat_id: str = "",
        notification_hour: int = 22,
    ) -> int:
        valid, msg = validate_password_strength(password)
        if not valid:
            raise ValueError(msg)

        res = self.sb.table("users").insert({
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": _hash_password(password),
            "role": role,
            "telegram_chat_id": telegram_chat_id.strip(),
            "notification_hour": notification_hour,
            "email_notifications_enabled": True,
            "failed_login_attempts": 0,
        }).execute()
        return res.data[0]["id"]

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        res = self.sb.table("users").select("*").eq("email", email.strip().lower()).limit(1).execute()
        return res.data[0] if (res and res.data) else None

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        res = self.sb.table("users").select(
            "id, name, email, role, telegram_chat_id, notification_hour, email_notifications_enabled, created_at"
        ).eq("id", user_id).limit(1).execute()
        return res.data[0] if (res and res.data) else None

    def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        user = self.get_by_email(email)
        if not user:
            return {"success": False, "error": "NOT_FOUND", "message": "E-mail não cadastrado no sistema."}

        # 1. Check lockout
        is_locked, remaining_sec = check_account_lockout(user)
        if is_locked:
            minutes = (remaining_sec + 59) // 60
            return {
                "success": False,
                "error": "LOCKED",
                "remaining_seconds": remaining_sec,
                "message": f"Conta bloqueada por excesso de tentativas. Tente em {minutes} minuto(s).",
            }

        # 2. Validate password
        if user["password_hash"] == _hash_password(password):
            self.sb.table("users").update(
                {"failed_login_attempts": 0, "locked_until": None}
            ).eq("id", user["id"]).execute()
            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"],
                    "telegram_chat_id": user.get("telegram_chat_id", ""),
                    "notification_hour": user.get("notification_hour", 22),
                },
            }

        # 3. Wrong password — increment counter
        current_fails = (user.get("failed_login_attempts") or 0) + 1
        if current_fails >= MAX_FAILED_ATTEMPTS:
            lockout_time = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            self.sb.table("users").update(
                {"failed_login_attempts": current_fails, "locked_until": lockout_time}
            ).eq("id", user["id"]).execute()
            return {
                "success": False,
                "error": "LOCKED",
                "remaining_seconds": LOCKOUT_MINUTES * 60,
                "message": f"Você errou a senha {MAX_FAILED_ATTEMPTS}x. Conta bloqueada por {LOCKOUT_MINUTES} minutos.",
            }
        else:
            remaining_tries = MAX_FAILED_ATTEMPTS - current_fails
            self.sb.table("users").update(
                {"failed_login_attempts": current_fails}
            ).eq("id", user["id"]).execute()
            return {
                "success": False,
                "error": "INVALID_PASSWORD",
                "remaining_attempts": remaining_tries,
                "message": f"Senha incorreta. {remaining_tries} tentativa(s) restante(s) antes do bloqueio de 3 min.",
            }

    def list_all(self) -> List[Dict[str, Any]]:
        res = self.sb.table("users").select(
            "id, name, email, role, telegram_chat_id, notification_hour, created_at"
        ).order("id").execute()
        return res.data or []

    def update_password(self, user_id: int, new_password: str):
        self.sb.table("users").update(
            {"password_hash": _hash_password(new_password)}
        ).eq("id", user_id).execute()


# ---------------------------------------------------------------------------
# ProductRepo (Supabase)
# ---------------------------------------------------------------------------

class ProductRepo:
    def __init__(self):
        self.sb = get_supabase()

    def _enrich_product(self, prod: dict) -> dict:
        """Adds latest_record, all_time_min/max and records_count to a product row."""
        pid = prod["id"]

        # Latest price record
        lr = self.sb.table("price_records").select("*").eq("product_id", pid)\
            .order("checked_at", desc=True).limit(1).execute()
        prod["latest_record"] = lr.data[0] if lr.data else None

        # All-time stats
        agg = self.sb.table("price_records").select(
            "min_price, max_price"
        ).eq("product_id", pid).execute()

        if agg.data:
            mins = [r["min_price"] for r in agg.data]
            maxs = [r["max_price"] for r in agg.data]
            prod["all_time_min"] = min(mins)
            prod["all_time_max"] = max(maxs)
            prod["records_count"] = len(agg.data)
        else:
            prod["all_time_min"] = None
            prod["all_time_max"] = None
            prod["records_count"] = 0

        return prod

    def get_all(
        self,
        user_id: Optional[int] = None,
        role: str = "admin",
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        query = self.sb.table("products").select("*, users(name, email, role)")
        if active_only:
            query = query.eq("is_active", True)
        if role != "admin" and user_id is not None:
            query = query.eq("user_id", user_id)
        query = query.order("id", desc=True)
        res = query.execute()
        products = res.data or []

        enriched = []
        for p in products:
            # Flatten nested user join
            user_info = p.pop("users", None) or {}
            p["owner_name"] = user_info.get("name", "")
            p["owner_email"] = user_info.get("email", "")
            p["owner_role"] = user_info.get("role", "")
            enriched.append(self._enrich_product(p))
        return enriched

    def get_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        res = self.sb.table("products").select("*").eq("id", product_id).limit(1).execute()
        if not res or not res.data:
            return None
        return self._enrich_product(res.data[0])

    def create(self, p: ProductCreate, user_id: Optional[int] = None) -> int:
        now = _now_iso()
        res = self.sb.table("products").insert({
            "user_id": user_id,
            "name": p.name.strip(),
            "brand": p.brand.strip(),
            "category": p.category or "Geral",
            "description": p.description or "",
            "search_query": p.search_query.strip(),
            "target_price": p.target_price,
            "image_url": p.image_url,
            "is_active": p.is_active if p.is_active is not None else True,
            "created_at": now,
            "updated_at": now,
        }).execute()
        return res.data[0]["id"]

    def update(self, product_id: int, p: ProductUpdate) -> bool:
        payload: dict = {"updated_at": _now_iso()}
        if p.name is not None:
            payload["name"] = p.name.strip()
        if p.brand is not None:
            payload["brand"] = p.brand.strip()
        if p.category is not None:
            payload["category"] = p.category
        if p.description is not None:
            payload["description"] = p.description
        if p.search_query is not None:
            payload["search_query"] = p.search_query.strip()
        if p.target_price is not None:
            payload["target_price"] = p.target_price
        if p.image_url is not None:
            payload["image_url"] = p.image_url
        if p.is_active is not None:
            payload["is_active"] = p.is_active

        res = self.sb.table("products").update(payload).eq("id", product_id).execute()
        return bool(res.data)

    def delete(self, product_id: int) -> bool:
        res = self.sb.table("products").delete().eq("id", product_id).execute()
        return bool(res.data)

    def add_price_record(
        self,
        product_id: int,
        scraped: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> int:
        now_str = _now_iso()
        res = self.sb.table("price_records").insert({
            "product_id": product_id,
            "checked_at": now_str,
            "min_price": scraped["min_price"],
            "max_price": scraped["max_price"],
            "avg_price": scraped["avg_price"],
            "best_store": scraped["best_store"],
            "best_url": scraped.get("best_url", ""),
            "highest_store": scraped.get("highest_store", ""),
            "recommendation": analysis["recommendation"],
            "recommendation_reason": analysis.get("recommendation_reason", ""),
            "delta_pct": analysis.get("delta_pct", 0.0),
            "delta_amount": analysis.get("delta_amount", 0.0),
        }).execute()
        record_id = res.data[0]["id"]

        # Insert individual store offers
        offers = scraped.get("offers", [])
        if offers:
            self.sb.table("store_offers").insert([
                {
                    "price_record_id": record_id,
                    "store_name": o["store_name"],
                    "product_title": o.get("product_title", ""),
                    "price": o["price"],
                    "url": o.get("url", ""),
                    "is_best": o.get("is_best", False),
                }
                for o in offers
            ]).execute()

        return record_id

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        res = self.sb.table("price_records").select("*").eq("id", record_id).limit(1).execute()
        if not res or not res.data:
            return None
        rec = res.data[0]
        offers_res = self.sb.table("store_offers").select(
            "store_name, product_title, price, url, is_best"
        ).eq("price_record_id", record_id).order("price").execute()
        rec["offers"] = offers_res.data or []
        return rec

    def get_history(self, product_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        res = self.sb.table("price_records").select(
            "id, checked_at, min_price, max_price, avg_price, best_store, recommendation, delta_pct"
        ).eq("product_id", product_id).order("checked_at").limit(limit).execute()
        return res.data or []

    def get_dashboard_stats(self) -> Dict[str, Any]:
        total = self.sb.table("products").select("id", count="exact").execute()
        active = self.sb.table("products").select("id", count="exact").eq("is_active", True).execute()
        records = self.sb.table("price_records").select("id", count="exact").execute()

        # Bargains: products whose latest record is EXCELLENT
        products = self.get_all()
        bargains = sum(
            1 for p in products
            if p.get("latest_record") and p["latest_record"].get("recommendation") == "EXCELLENT"
        )
        avg_prices = [
            p["latest_record"]["min_price"]
            for p in products
            if p.get("latest_record")
        ]
        avg_market = round(sum(avg_prices) / len(avg_prices), 2) if avg_prices else 0.0

        return {
            "total_products": total.count or 0,
            "active_products": active.count or 0,
            "today_bargains": bargains,
            "total_price_checks": records.count or 0,
            "average_market_price": avg_market,
        }
