"""Сервис карточек — просмотр отправленных, реакции по карточке."""

from datetime import datetime

from admin_bot.services.db_service import get_connection


def get_cards_today() -> dict:
    """Получить сводку по карточкам за сегодня."""
    today_start = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"

    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM sent_ads WHERE first_sent_at >= ?",
            (today_start,)
        ).fetchone()["cnt"]

        # Карточки с реакциями
        with_reactions = conn.execute(
            """SELECT COUNT(DISTINCT s.stable_car_key) as cnt
               FROM sent_ads s
               INNER JOIN feedback f ON s.stable_car_key = f.card_id
               WHERE s.first_sent_at >= ?""",
            (today_start,)
        ).fetchone()["cnt"]

        # Карточки без реакций
        without_reactions = total - with_reactions

        # Список карточек (последние 20)
        cards = conn.execute(
            """SELECT s.stable_car_key, s.card_id, s.title, s.price,
                      s.mileage, s.region, s.year, s.model_id,
                      s.first_sent_at, s.mobile_url, s.send_count,
                      (SELECT COUNT(*) FROM feedback f WHERE f.card_id = s.stable_car_key) as reaction_count
               FROM sent_ads s
               WHERE s.first_sent_at >= ?
               ORDER BY s.first_sent_at DESC
               LIMIT 20""",
            (today_start,)
        ).fetchall()

        cards_list = []
        for c in cards:
            cards_list.append({
                "stable_car_key": c["stable_car_key"],
                "card_id": c["card_id"],
                "title": c["title"],
                "price": c["price"],
                "mileage": c["mileage"],
                "region": c["region"],
                "year": c["year"],
                "model_id": c["model_id"],
                "first_sent_at": c["first_sent_at"],
                "mobile_url": c["mobile_url"],
                "send_count": c["send_count"],
                "reaction_count": c["reaction_count"],
            })

        return {
            "total": total,
            "with_reactions": with_reactions,
            "without_reactions": without_reactions,
            "cards": cards_list,
        }
    finally:
        conn.close()


def get_card_detail(stable_car_key: str) -> dict | None:
    """Получить детальную информацию по карточке."""
    conn = get_connection()
    try:
        card = conn.execute(
            """SELECT stable_car_key, card_id, title, price, mileage,
                      region, year, model_id, engine, transmission, drive,
                      first_sent_at, mobile_url, send_count
               FROM sent_ads
               WHERE stable_car_key = ?
               LIMIT 1""",
            (stable_car_key,)
        ).fetchone()

        if not card:
            return None

        card_data = dict(card)

        # Реакции по карточке
        reactions = conn.execute(
            """SELECT u.username, u.first_name, f.action, f.comment, f.created_at
               FROM feedback f
               LEFT JOIN telegram_users u ON f.telegram_user_id = u.telegram_id
               WHERE f.card_id = ?
               ORDER BY f.created_at ASC""",
            (stable_car_key,)
        ).fetchall()

        card_data["reactions"] = [dict(r) for r in reactions]

        return card_data
    finally:
        conn.close()
