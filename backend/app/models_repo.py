import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.schemas import ProductCreate, ProductUpdate
from app.auth_utils import validate_password_strength, check_account_lockout, LOCKOUT_MINUTES, MAX_FAILED_ATTEMPTS

class UserRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.strip().encode('utf-8')).hexdigest()

    def create(self, name: str, email: str, password: str, role: str = "user", telegram_chat_id: str = "", notification_hour: int = 22) -> int:
        valid, msg = validate_password_strength(password)
        if not valid:
            raise ValueError(msg)

        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        pwd_hash = self.hash_password(password)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, telegram_chat_id, notification_hour, email_notifications_enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (name.strip(), email.strip().lower(), pwd_hash, role, telegram_chat_id.strip(), notification_hour, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT id, name, email, role, telegram_chat_id, notification_hour, email_notifications_enabled, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        user = self.get_by_email(email)
        if not user:
            return {"success": False, "error": "NOT_FOUND", "message": "E-mail não cadastrado no sistema."}

        # 1. Check if user account is currently locked
        is_locked, remaining_sec = check_account_lockout(user)
        if is_locked:
            minutes = (remaining_sec + 59) // 60
            return {
                "success": False,
                "error": "LOCKED",
                "remaining_seconds": remaining_sec,
                "message": f"Conta temporariamente bloqueada por excesso de tentativas. Tente novamente em {minutes} minuto(s) ({remaining_sec}s)."
            }

        # 2. Check password match
        if user["password_hash"] == self.hash_password(password):
            # Success! Reset failed attempts counter
            self.conn.execute("UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?", (user["id"],))
            self.conn.commit()
            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"],
                    "telegram_chat_id": user.get("telegram_chat_id", ""),
                    "notification_hour": user.get("notification_hour", 22)
                }
            }

        # 3. Password failed: increment counter
        current_fails = (user.get("failed_login_attempts") or 0) + 1
        cursor = self.conn.cursor()

        if current_fails >= MAX_FAILED_ATTEMPTS:
            # Lock out account for 3 minutes
            lockout_time = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            cursor.execute("UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?", 
                           (current_fails, lockout_time, user["id"]))
            self.conn.commit()
            return {
                "success": False,
                "error": "LOCKED",
                "remaining_seconds": LOCKOUT_MINUTES * 60,
                "message": f"Você errou a senha 4 vezes consecutivas. Sua conta foi bloqueada por {LOCKOUT_MINUTES} minutos por segurança."
            }
        else:
            remaining_tries = MAX_FAILED_ATTEMPTS - current_fails
            cursor.execute("UPDATE users SET failed_login_attempts = ? WHERE id = ?", (current_fails, user["id"]))
            self.conn.commit()
            return {
                "success": False,
                "error": "INVALID_PASSWORD",
                "remaining_attempts": remaining_tries,
                "message": f"Senha incorreta. Você ainda tem {remaining_tries} tentativa(s) antes do bloqueio temporário de 3 minutos."
            }

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT id, name, email, role, telegram_chat_id, notification_hour, created_at FROM users ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]

class ProductRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_all(self, user_id: Optional[int] = None, role: str = "admin", active_only: bool = False) -> List[Dict[str, Any]]:
        conditions = []
        params = []

        if active_only:
            conditions.append("p.is_active = 1")

        # If user is NOT admin, restrict strictly to their own products
        if role != "admin" and user_id is not None:
            conditions.append("p.user_id = ?")
            params.append(user_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT p.*, u.name as owner_name, u.email as owner_email, u.role as owner_role
            FROM products p
            LEFT JOIN users u ON p.user_id = u.id
            {where_clause}
            ORDER BY p.id DESC
        """

        rows = self.conn.execute(query, params).fetchall()
        products = []
        for r in rows:
            prod = dict(r)
            # Fetch latest record
            latest = self.conn.execute("""
                SELECT * FROM price_records 
                WHERE product_id = ? 
                ORDER BY checked_at DESC 
                LIMIT 1
            """, (prod["id"],)).fetchone()
            
            prod["latest_record"] = dict(latest) if latest else None

            # Fetch all-time min and max
            min_max = self.conn.execute("""
                SELECT MIN(min_price) as all_time_min, MAX(max_price) as all_time_max, COUNT(*) as cnt
                FROM price_records 
                WHERE product_id = ?
            """, (prod["id"],)).fetchone()

            prod["all_time_min"] = min_max["all_time_min"] if min_max else None
            prod["all_time_max"] = min_max["all_time_max"] if min_max else None
            prod["records_count"] = min_max["cnt"] if min_max else 0
            prod["is_active"] = bool(prod["is_active"])

            products.append(prod)
        return products

    def get_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return None
        prod = dict(row)
        latest = self.conn.execute("""
            SELECT * FROM price_records 
            WHERE product_id = ? 
            ORDER BY checked_at DESC 
            LIMIT 1
        """, (prod["id"],)).fetchone()
        
        prod["latest_record"] = dict(latest) if latest else None
        
        min_max = self.conn.execute("""
            SELECT MIN(min_price) as all_time_min, MAX(max_price) as all_time_max, COUNT(*) as cnt
            FROM price_records 
            WHERE product_id = ?
        """, (prod["id"],)).fetchone()

        prod["all_time_min"] = min_max["all_time_min"] if min_max else None
        prod["all_time_max"] = min_max["all_time_max"] if min_max else None
        prod["records_count"] = min_max["cnt"] if min_max else 0
        prod["is_active"] = bool(prod["is_active"])
        return prod

    def create(self, p: ProductCreate, user_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO products (user_id, name, brand, category, description, search_query, target_price, image_url, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            p.name.strip(),
            p.brand.strip(),
            p.category or "Geral",
            p.description or "",
            p.search_query.strip(),
            p.target_price,
            p.image_url,
            1 if p.is_active else 0,
            now,
            now
        ))
        self.conn.commit()
        return cursor.lastrowid

    def update(self, product_id: int, p: ProductUpdate) -> bool:
        fields = []
        values = []
        now = datetime.now().isoformat()

        if p.name is not None:
            fields.append("name = ?")
            values.append(p.name.strip())
        if p.brand is not None:
            fields.append("brand = ?")
            values.append(p.brand.strip())
        if p.category is not None:
            fields.append("category = ?")
            values.append(p.category)
        if p.description is not None:
            fields.append("description = ?")
            values.append(p.description)
        if p.search_query is not None:
            fields.append("search_query = ?")
            values.append(p.search_query.strip())
        if p.target_price is not None:
            fields.append("target_price = ?")
            values.append(p.target_price)
        if p.image_url is not None:
            fields.append("image_url = ?")
            values.append(p.image_url)
        if p.is_active is not None:
            fields.append("is_active = ?")
            values.append(1 if p.is_active else 0)

        if not fields:
            return True

        fields.append("updated_at = ?")
        values.append(now)
        values.append(product_id)

        sql = f"UPDATE products SET {', '.join(fields)} WHERE id = ?"
        cursor = self.conn.execute(sql, values)
        self.conn.commit()
        return cursor.rowcount > 0

    def delete(self, product_id: int) -> bool:
        # Delete associated records and offers
        cursor = self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def add_price_record(self, product_id: int, scraped: Dict[str, Any], analysis: Dict[str, Any]) -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO price_records (
                product_id, checked_at, min_price, max_price, avg_price, 
                best_store, best_url, highest_store, recommendation, 
                recommendation_reason, delta_pct, delta_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            now_str,
            scraped["min_price"],
            scraped["max_price"],
            scraped["avg_price"],
            scraped["best_store"],
            scraped.get("best_url", ""),
            scraped.get("highest_store", ""),
            analysis["recommendation"],
            analysis.get("recommendation_reason", ""),
            analysis.get("delta_pct", 0.0),
            analysis.get("delta_amount", 0.0)
        ))
        record_id = cursor.lastrowid

        # Insert store offers
        offers = scraped.get("offers", [])
        for o in offers:
            cursor.execute("""
                INSERT INTO store_offers (price_record_id, store_name, product_title, price, url, is_best)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                o["store_name"],
                o.get("product_title", ""),
                o["price"],
                o.get("url", ""),
                1 if o.get("is_best") else 0
            ))

        self.conn.commit()
        return record_id

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM price_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return None
        rec = dict(row)
        offers = self.conn.execute("""
            SELECT store_name, product_title, price, url, is_best 
            FROM store_offers 
            WHERE price_record_id = ? 
            ORDER BY price ASC
        """, (record_id,)).fetchall()
        rec["offers"] = [dict(o) for o in offers]
        return rec

    def get_history(self, product_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        rows = self.conn.execute("""
            SELECT id, checked_at, min_price, max_price, avg_price, best_store, recommendation, delta_pct
            FROM price_records 
            WHERE product_id = ? 
            ORDER BY checked_at ASC 
            LIMIT ?
        """, (product_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_dashboard_stats(self) -> Dict[str, Any]:
        total_products = self.conn.execute("SELECT COUNT(*) as c FROM products").fetchone()["c"]
        active_products = self.conn.execute("SELECT COUNT(*) as c FROM products WHERE is_active = 1").fetchone()["c"]
        total_records = self.conn.execute("SELECT COUNT(*) as c FROM price_records").fetchone()["c"]

        # Today's bargains (recommendation = 'EXCELLENT' on latest record)
        bargains = 0
        products = self.get_all()
        for p in products:
            latest = p.get("latest_record")
            if latest and latest.get("recommendation") == "EXCELLENT":
                bargains += 1

        # Average market price across active products
        avg_prices = [p["latest_record"]["min_price"] for p in products if p.get("latest_record")]
        avg_market = round(sum(avg_prices) / len(avg_prices), 2) if avg_prices else 0.0

        return {
            "total_products": total_products,
            "active_products": active_products,
            "today_bargains": bargains,
            "total_price_checks": total_records,
            "average_market_price": avg_market
        }
