from card_data_loader import load_card_data
cards = load_card_data()
c = cards.get('171340559', {})
print(f'Found: {bool(c)}')
print(f'raw_text len: {len(c.get("mobile_detail_raw_text", ""))}')
raw = c.get('mobile_detail_raw_text', '')
idx = raw.find('Комментарий продавца')
print(f'Комментарий at: {idx}')
if idx != -1:
    print(f'Snippet: {raw[idx:idx+100]}')
