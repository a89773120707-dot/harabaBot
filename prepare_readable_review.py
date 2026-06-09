"""prepare_readable_review.py — Блок 14.1-14.2: читаемый manual review"""
import yaml
import json
import re
from pathlib import Path
from base import RESULTS_DIR

# Загружаем результаты скоринга
with open(RESULTS_DIR / "config_scoring_test_500.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

results = data.get("results", [])

# Загружаем реальные карточки для получения price/year/mileage
with open(RESULTS_DIR / "real_cards_matched_17.json", "r", encoding="utf-8") as f:
    real_cards = json.load(f)

# Создаём lookup по url
card_lookup = {}
for rc in real_cards:
    url = rc.get("url", "")
    card_lookup[url] = rc

# Сортируем по score
sorted_results = sorted(results, key=lambda r: r.get("score", 0), reverse=True)

# Разделяем по decision
by_decision = {}
for r in sorted_results:
    d = r.get("decision", "unknown")
    if d not in by_decision:
        by_decision[d] = []
    by_decision[d].append(r)

# Извлекаем price/mileage/year из explanation
def extract_from_explanation(expl):
    """Парсит price и mileage из explanation строки."""
    price = None
    mileage = None
    m_price = re.search(r"Price:\s+([\d\s,]+)\s*₽", expl)
    if m_price:
        price = int(m_price.group(1).replace(",", "").replace(" ", "").strip())
    m_mileage = re.search(r"Mileage:\s+([\d\s,]+)\s*км", expl)
    if m_mileage:
        mileage = int(m_mileage.group(1).replace(",", "").replace(" ", "").strip())
    return price, mileage

# Собираем карточки для ручной проверки:
# - все good (9)
# - топ-10 watch
# - топ-5 reject (по score)
# - топ-5 weak
manual_cards = []
for r in by_decision.get("good_candidate", []) + by_decision.get("watch", [])[:10] + by_decision.get("reject", [])[:5] + by_decision.get("weak", [])[:5]:
    url = r.get("url", "")
    rc = card_lookup.get(url, {})

    price = r.get("price") or rc.get("price")
    mileage = r.get("mileage") or rc.get("mileage")
    year = r.get("year") or rc.get("year")

    # Если всё ещё null — парсим из explanation
    if not price or not mileage:
        p, m = extract_from_explanation(r.get("explanation", ""))
        price = price or p
        mileage = mileage or m

    card = {
        "id": f"card_{len(manual_cards)+1:03d}",
        "title": r.get("title", rc.get("title", "")),
        "model_id": r.get("model_id", ""),
        "price": price,
        "year": year,
        "mileage": mileage,
        "score": r.get("score", 0),
        "decision": r.get("decision", ""),
        "url": url,
        "pluses": r.get("bonus_reasons", []),
        "minuses": r.get("penalty_reasons", []),
        "reject_reasons": r.get("reject_reasons", []),
        "warnings": r.get("warnings", []),
        "human_verdict": None,
        "human_comment": None,
    }
    manual_cards.append(card)

# Сохраняем YAML
yaml_out = RESULTS_DIR / "manual_review_top_20.yaml"
with open(yaml_out, "w", encoding="utf-8") as f:
    yaml.dump({
        "manual_review": manual_cards,
        "instructions": """
human_verdict варианты:
  - buy: реально купил бы в салон
  - maybe: возможно, стоит посмотреть
  - skip: не интересно / мусор

human_comment: свободный комментарий (дорого, пустая, хороший вариант и т.д.)
"""
    }, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

print(f"💾 {yaml_out}: {len(manual_cards)} карточек")

# Создаём читаемый markdown
md_lines = [
    "# Manual Review — Реальные карточки из Haraba",
    "",
    f"Всего карточек: {len(manual_cards)}",
    "",
    "## Инструкции",
    "",
    "Для каждой карточки укажите:",
    "- `buy` — реально купил бы в салон",
    "- `maybe` — возможно, стоит посмотреть",
    "- `skip` — не интересно / мусор",
    "",
    "---",
    "",
]

for i, c in enumerate(manual_cards, 1):
    emoji = {"good_candidate": "✅", "watch": "👀", "weak": "⚠️", "reject": "❌"}.get(c["decision"], "❓")
    md_lines.append(f"## {i}. {c['title']} ({c.get('year', '?')})")
    md_lines.append("")
    md_lines.append(f"**Score:** {c['score']}/100")
    md_lines.append(f"**Decision:** {c['decision']} {emoji}")
    md_lines.append(f"**Price:** {c['price']:,} ₽" if c['price'] else "**Price:** неизвестна")
    md_lines.append(f"**Mileage:** {c['mileage']:,} км" if c['mileage'] else "**Mileage:** неизвестен")
    md_lines.append(f"**Model:** {c['model_id']}")
    md_lines.append("")

    if c.get("pluses"):
        md_lines.append("Плюсы:")
        for p in c["pluses"]:
            md_lines.append(f"- ✅ {p}")
        md_lines.append("")

    if c.get("minuses"):
        md_lines.append("Минусы:")
        for m in c["minuses"]:
            md_lines.append(f"- ⚠️ {m}")
        md_lines.append("")

    if c.get("reject_reasons"):
        md_lines.append("Причины reject:")
        for r in c["reject_reasons"]:
            md_lines.append(f"- ❌ {r}")
        md_lines.append("")

    md_lines.append(f"Ссылка: [{c['url']}]({c['url']})" if c.get("url") and not c["url"].startswith("test://") else "")
    md_lines.append("")
    md_lines.append("Твоя оценка:")
    md_lines.append("- [ ] buy")
    md_lines.append("- [ ] maybe")
    md_lines.append("- [ ] skip")
    md_lines.append("")
    md_lines.append("Комментарий:")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

md_path = RESULTS_DIR / "manual_review_readable.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"💾 {md_path}")

# Считаем распределение
from collections import Counter
dec_counts = Counter(c["decision"] for c in manual_cards)
print(f"\nРаспределение:")
for d, cnt in dec_counts.most_common():
    print(f"  {d}: {cnt}")
