"""Тест новой dedup v2 логики."""
from feedback_store import check_dedup, mark_sent, update_last_seen, reset_sent_ads, get_sent_stats

# Test card 1
card1 = {
    "card_id": "TEST001",
    "title": "Test Car",
    "url": "https://haraba.ru/common/click?id=TEST001&source=1",
    "mobile_url": "https://m.haraba.ru/search/car/TEST001",
    "model_id": "test_model",
    "year": 2020,
    "price": 1500000,
    "mileage": 50000,
    "region": "Москва",
}

print("=== Test 1: New card ===")
status = check_dedup(card1)
print(f"  check_dedup -> {status}")
assert status == "new", f"Expected 'new', got '{status}'"
print("  PASS")

print("\n=== Test 2: Mark as sent ===")
mark_sent(card1, status="new")
status = check_dedup(card1)
print(f"  check_dedup -> {status}")
assert status == "same_price", f"Expected 'same_price', got '{status}'"
print("  PASS")

print("\n=== Test 3: Same price -> skip ===")
status = check_dedup(card1)
assert status == "same_price"
print(f"  check_dedup -> {status} (skip)")
print("  PASS")

print("\n=== Test 4: Price drop -> send ===")
card1_drop = dict(card1, price=1400000)
status = check_dedup(card1_drop)
print(f"  check_dedup -> {status}")
assert status == "price_drop", f"Expected 'price_drop', got '{status}'"
mark_sent(card1_drop, status="price_drop")
print("  PASS")

print("\n=== Test 5: Price increase -> skip ===")
card1_up = dict(card1, price=1600000)
status = check_dedup(card1_up)
print(f"  check_dedup -> {status}")
assert status == "price_increased", f"Expected 'price_increased', got '{status}'"
update_last_seen(card1_up)
print("  PASS")

print("\n=== Test 6: Stats ===")
stats = get_sent_stats()
print(f"  Stats: {stats}")

print("\n=== All tests passed ===")
