"""add_transmission.py — add transmission field to config_loader and search_expander."""
import sys

# Fix config_loader_8.py
with open('config_loader_8.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    # After 'condition: Optional[str] = None', add transmission and mileage_max
    if 'condition: Optional[str] = None' in line:
        indent = '    '
        new_lines.append(indent + 'mileage_max: Optional[int] = None\n')
        new_lines.append(indent + 'transmission: Optional[str] = None\n')

with open('config_loader_8.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('config_loader_8.py updated')

# Now fix the extraction and return
with open('config_loader_8.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'transmission = search_filters.get("transmission")' not in content:
    content = content.replace(
        'condition = search_filters.get("condition")',
        'condition = search_filters.get("condition")\n    mileage_max = search_filters.get("mileage_max")\n    transmission = search_filters.get("transmission")'
    )

if 'transmission=transmission,' not in content:
    content = content.replace(
        'condition=condition,',
        'condition=condition,\n        mileage_max=int(mileage_max) if mileage_max else None,\n        transmission=transmission,'
    )

with open('config_loader_8.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('config_loader_8.py extraction fixed')

# Fix search_expander_8.py
with open('search_expander_8.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if 'condition: Optional[str] = None' in line:
        indent = '    '
        new_lines.append(indent + 'mileage_max: Optional[int] = None\n')
        new_lines.append(indent + 'transmission: Optional[str] = None\n')

with open('search_expander_8.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('search_expander_8.py updated')

# Fix return in search_expander
with open('search_expander_8.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'transmission=search.transmission,' not in content:
    content = content.replace(
        'condition=search.condition,',
        'condition=search.condition,\n        mileage_max=search.mileage_max,\n        transmission=search.transmission,'
    )

with open('search_expander_8.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('search_expander_8.py return fixed')
