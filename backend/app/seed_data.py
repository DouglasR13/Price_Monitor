from datetime import datetime, timedelta
import random
from app.database import get_db

SAMPLE_PRODUCTS = [
    {
        "name": "PlayStation 5 Slim Edição Digital",
        "brand": "Sony",
        "category": "Games",
        "description": "Console PlayStation 5 Slim com 1TB SSD e controle sem fio DualSense",
        "search_query": "PlayStation 5 Slim Edicao Digital",
        "target_price": 3500.0,
        "image_url": "https://m.media-amazon.com/images/I/51rPq4+a1vL._AC_SL1000_.jpg",
        "base_min": 3599.0,
        "base_avg": 3890.0,
        "base_max": 4299.0,
        "stores": ["Amazon", "Mercado Livre", "KaBuM!", "Magazine Luiza"],
        "urls": {
            "Amazon": "https://www.amazon.com.br",
            "KaBuM!": "https://www.kabum.com.br"
        }
    },
    {
        "name": "Fone Sony WH-1000XM5 Noise Cancelling",
        "brand": "Sony",
        "category": "Áudio",
        "description": "Headphone Over-Ear Bluetooth com Cancelamento Ativo de Ruído e Microfone",
        "search_query": "Sony WH-1000XM5",
        "target_price": 2200.0,
        "image_url": "https://i.zst.com.br/thumbs/45/35/32/-1264316215.jpg",
        "base_min": 2149.0,
        "base_avg": 2480.0,
        "base_max": 2899.0,
        "stores": ["Amazon", "Mercado Livre", "Fast Shop", "Magazine Luiza"],
        "urls": {
            "Amazon": "https://www.amazon.com.br",
            "Fast Shop": "https://www.fastshop.com.br"
        }
    },
    {
        "name": "iPhone 15 128GB Preto",
        "brand": "Apple",
        "category": "Smartphones",
        "description": "Apple iPhone 15 com tela Super Retina XDR de 6.1\", Dynamic Island e Câmera 48MP",
        "search_query": "iPhone 15 128GB",
        "target_price": 4600.0,
        "image_url": "https://m.media-amazon.com/images/I/71657TiFeHL._AC_SL1500_.jpg",
        "base_min": 4799.0,
        "base_avg": 5290.0,
        "base_max": 5999.0,
        "stores": ["Mercado Livre", "Amazon", "Magazine Luiza", "Casas Bahia"],
        "urls": {
            "Mercado Livre": "https://lista.mercadolivre.com.br",
            "Magazine Luiza": "https://www.magazineluiza.com.br"
        }
    },
    {
        "name": "Smart TV LG OLED evo 55\" 4K C3",
        "brand": "LG",
        "category": "TV e Vídeo",
        "description": "Smart TV 55 polegadas OLED 120Hz com Dolby Vision, G-Sync e processador α9 Gen6",
        "search_query": "LG OLED 55 C3",
        "target_price": 5300.0,
        "image_url": "https://m.media-amazon.com/images/I/71r4zKzF5OL._AC_SL1500_.jpg",
        "base_min": 5199.0,
        "base_avg": 5790.0,
        "base_max": 6499.0,
        "stores": ["Fast Shop", "KaBuM!", "Amazon", "Carrefour"],
        "urls": {
            "KaBuM!": "https://www.kabum.com.br",
            "Fast Shop": "https://www.fastshop.com.br"
        }
    }
]

def seed_database_if_empty():
    """Populates database with sample users, products and 14 days of historical price records."""
    from app.models_repo import UserRepo

    with get_db() as conn:
        user_repo = UserRepo(conn)
        # Ensure default Admin and Demo user exist
        admin_user = user_repo.get_by_email("admin@radar.com")
        if not admin_user:
            admin_id = user_repo.create(
                name="Administrador",
                email="admin@radar.com",
                password="Admin@123",
                role="admin",
                telegram_chat_id=""
            )
        else:
            admin_id = admin_user["id"]
            # Ensure password hash is updated to Admin@123
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (UserRepo.hash_password("Admin@123"), admin_id))

        demo_user = user_repo.get_by_email("usuario@demo.com")
        if not demo_user:
            demo_id = user_repo.create(
                name="Carlos Silva",
                email="usuario@demo.com",
                password="User@123",
                role="user",
                telegram_chat_id=""
            )
        else:
            demo_id = demo_user["id"]
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (UserRepo.hash_password("User@123"), demo_id))

        # If products already exist, update any NULL user_id
        conn.execute("UPDATE products SET user_id = ? WHERE user_id IS NULL AND id % 2 = 1", (admin_id,))
        conn.execute("UPDATE products SET user_id = ? WHERE user_id IS NULL", (demo_id,))
        conn.commit()

        count = conn.execute("SELECT COUNT(*) as count FROM products").fetchone()["count"]
        if count > 0:
            return  # Products already seeded

        now = datetime.now()

        for idx, item in enumerate(SAMPLE_PRODUCTS):
            created_at = (now - timedelta(days=14)).isoformat()
            cursor = conn.cursor()
            # Assign first 2 to Admin, last 2 to Demo User
            owner_id = admin_id if idx < 2 else demo_id

            cursor.execute("""
                INSERT INTO products (user_id, name, brand, category, description, search_query, target_price, image_url, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                owner_id,
                item["name"],
                item["brand"],
                item["category"],
                item["description"],
                item["search_query"],
                item["target_price"],
                item["image_url"],
                created_at,
                now.isoformat()
            ))
            product_id = cursor.lastrowid

            # Generate 14 days of daily records with realistic market curve
            base_p = item["base_min"]
            previous_min = base_p

            for day_offset in range(14, -1, -1):
                record_time = (now - timedelta(days=day_offset, hours=random.randint(8, 11), minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S")

                # Curve simulation
                if day_offset == 0:
                    # Today: make one product an amazing deal, one normal, one high
                    if "Sony WH-1000XM5" in item["name"]:
                        # All-time low deal today!
                        curr_min = 2089.0
                    elif "PlayStation" in item["name"]:
                        curr_min = 3499.0  # Hit target price!
                    elif "LG OLED" in item["name"]:
                        curr_min = 5150.0  # Good deal
                    else:
                        curr_min = round(base_p * 1.04, 2)  # High
                else:
                    drift = random.uniform(-0.025, 0.025)
                    curr_min = round(base_p * (1.0 + drift + (day_offset * 0.003)), 2)

                curr_max = round(curr_min * random.uniform(1.15, 1.25), 2)
                curr_avg = round((curr_min + curr_max) / 2.0, 2)

                delta_amount = round(curr_min - previous_min, 2)
                delta_pct = round(((curr_min - previous_min) / previous_min) * 100, 2)
                previous_min = curr_min

                best_store = random.choice(item["stores"])
                highest_store = [s for s in item["stores"] if s != best_store][0]
                best_url = item["urls"].get(best_store, "https://www.google.com/search?q=" + item["search_query"])

                # Determine recommendation
                if curr_min <= item["target_price"]:
                    rec = "EXCELLENT"
                    rec_reason = f"🎯 Atingiu sua meta de preço! Valor de R$ {curr_min:,.2f} está abaixo do alvo (R$ {item['target_price']:,.2f})."
                elif day_offset == 0 and "Sony" in item["name"]:
                    rec = "EXCELLENT"
                    rec_reason = "🔥 Menor Preço Histórico! Novo recorde de baixa dos últimos 30 dias na Amazon."
                elif curr_min > curr_avg * 0.98:
                    rec = "HIGH"
                    rec_reason = "⏳ Preço em alta recente (+4.2% vs média semanal). Recomendamos aguardar nova oscilação."
                else:
                    rec = "NORMAL"
                    rec_reason = "Preço estável, oscilando dentro da faixa de preço regular do mercado."

                cursor.execute("""
                    INSERT INTO price_records 
                    (product_id, checked_at, min_price, max_price, avg_price, best_store, best_url, highest_store, recommendation, recommendation_reason, delta_pct, delta_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id,
                    record_time,
                    curr_min,
                    curr_max,
                    curr_avg,
                    best_store,
                    best_url,
                    highest_store,
                    rec,
                    rec_reason,
                    delta_pct,
                    delta_amount
                ))
                record_id = cursor.lastrowid

                # Store offers for this run
                for store in item["stores"]:
                    s_price = curr_min if store == best_store else round(curr_min * random.uniform(1.04, 1.20), 2)
                    cursor.execute("""
                        INSERT INTO store_offers (price_record_id, store_name, product_title, price, url, is_best)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        record_id,
                        store,
                        f"{item['name']} - {store}",
                        s_price,
                        item["urls"].get(store, best_url),
                        1 if store == best_store else 0
                    ))

        conn.commit()
