from region_parser import parse_region
tests = [
    'Котельники', 'Чехов', 'Новомосковск',
    'Кесова Гора', 'Подольск', 'Щербинка',
    'Электросталь', 'Тверская область',
    'Тульская область', 'Владимир', 'Ярославль'
]
with open('results/rp_test.txt', 'w', encoding='utf-8') as f:
    for t in tests:
        r = parse_region(t)
        f.write(f'{t} -> {r}\n')
print(f'Tested {len(tests)} regions')
