"""
БЛОК 4: model_matcher.py — определение model_id по карточке
"""
import re

# Aliases для matching
ALIASES = {
    # ready_8
    "kia_sorento_prime": ["sorento prime", "соренто прайм", "sorento_prime"],
    "volkswagen_touareg_nf": ["touareg", "туарег"],
    "volkswagen_tiguan": ["tiguan", "тигуан"],
    "nissan_xtrail": ["x-trail", "x trail", "икстрейл", "xtrail"],
    "nissan_qashqai_j11": ["qashqai", "кашк", "qashqay"],
    "ford_kuga": ["kuga", "куга"],
    "mercedes_glk_220_cdi": ["glk", "глк"],
    "volkswagen_multivan_t5": ["multivan", "мультивэн", "мультиван"],
    # partial_9
    "audi_q5": ["q5"],
    "hyundai_grand_santa_fe": ["grand santa fe", "санта фе гранд", "santa_fe_grand", "santa fe grand"],
    "hyundai_santa_fe": ["santa fe", "санта фе"],
    "kia_sorento": ["sorento", "соренто"],
    "kia_sportage": ["sportage", "спортаж"],
    "mazda_cx5": ["cx-5", "cx5", "сх-5"],
    "mitsubishi_pajero_iv": ["pajero", "паджеро"],
    "volvo_xc90": ["xc90"],
}


def _build_index(config: dict) -> dict:
    """Строит индекс: (brand_lower, model_lower) -> model_id + aliases."""
    index = {}

    for m in config.get("models", []):
        mid = m["id"]
        brand = m.get("brand", "").lower()
        model = m.get("model", "").lower()

        # Основной ключ
        key = (brand, model)
        index[key] = mid

        # Aliases
        for alias in ALIASES.get(mid, []):
            index[(brand, alias.lower())] = mid

    return index


def match_card_to_model(card: dict, config: dict) -> str | None:
    """Определяет model_id для карточки.

    Порядок:
    1. Прямой match по brand + model из конфига
    2. Match по title через aliases
    3. Match по brand + model через aliases
    """
    index = _build_index(config)
    title = (card.get("title", "")).lower()
    brand = (card.get("brand", "")).lower()
    model = (card.get("model", "")).lower()

    # 1. Прямой match brand + model
    key = (brand, model)
    if key in index:
        return index[key]

    # 2. Match по title через aliases
    for mid, aliases in ALIASES.items():
        for alias in aliases:
            if alias.lower() in title:
                return mid

    # 3. Partial match — ищем brand в title + model в title
    for m in config.get("models", []):
        mid = m["id"]
        mb = m.get("brand", "").lower()
        mm = m.get("model", "").lower()
        if mb in title and mm in title:
            return mid

    return None
