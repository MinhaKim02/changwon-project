#!/usr/bin/env bash
# 원본(data/raw) → 결과(data/processed) → 그림·보고서(report) → 대시보드(dashboard) 전체 재생성
set -euo pipefail
cd "$(dirname "$0")"
python3 01_inventory.py
python3 02_validate.py
python3 03_screen_zones.py
python3 04_result_table.py
python3 05_crosscheck_official.py
python3 06_drt_scenario.py
python3 07_figures.py
python3 08_build_report.py
python3 09_dashboard.py
