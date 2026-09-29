#!/usr/bin/env bash
# 원본(data/raw) → 결과(data/processed) 전체 재생성
set -euo pipefail
cd "$(dirname "$0")"
python3 01_inventory.py
python3 02_validate.py
python3 03_screen_zones.py
python3 04_result_table.py
python3 05_crosscheck_official.py
