#!/bin/bash
# Haraba Mini Pipeline Runner
# Запуск: ./run_pipeline.sh

# Переход в директорию проекта
cd /opt/haraba-mini

# Активация виртуального окружения
source venv/bin/activate

# Запуск pipeline
echo "[$(date)] Starting pipeline..."
python run_daily_pipeline.py --send --limit 3 >> logs/pipeline.log 2>&1

echo "[$(date)] Pipeline finished."
