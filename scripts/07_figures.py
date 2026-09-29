"""보고서·대시보드용 그림(PNG). data/processed 결과만 읽는다.
출력: report/figures/fig1_map.png, fig2_bands.png, fig3_scenario.png, fig4_boarding.png
"""
import json

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from common import OUT, ROOT, load_bis, route_stops

FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
for f in font_manager.findSystemFonts():
    if "NotoSansCJK-Regular" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "figure.dpi": 150})
C_VALLEY, C_JD, C_ADD, INK, MUTED = "#eb6834", "#2a78d6", "#b9b8b2", "#0b0b0b", "#8a8984"
BANDS = ["~07시", "07–09시", "09–12시", "12–15시", "15–18시", "18–20시", "20시~"]

res = pd.read_csv(OUT / "result_table_1.csv", encoding="utf-8-sig")
defs = json.loads((OUT / "result_table_1_place_definitions.json").read_text(encoding="utf-8"))
ids = lambda k: {int(x.split("(")[1].rstrip(")")) for x in defs[k]}

# ---- 그림 1: 위치도(정류소 좌표) -------------------------------------------------
rs = route_stops(load_bis())
allst = rs.drop_duplicates("spotId")
r73 = rs[rs.routeId == "379000730"].sort_values("spotSn")
fig, ax = plt.subplots(figsize=(6.4, 5.2))
box = allst[(allst.xCrdnt.between(128.36, 128.62)) & (allst.yCrdnt.between(35.08, 35.27))]
ax.scatter(box.xCrdnt, box.yCrdnt, s=2, color="#d9d8d3", lw=0, label="시내버스 정류소(전체)")
ax.plot(r73.xCrdnt, r73.yCrdnt, color=MUTED, lw=1.2, label="73번 경로")
for key, col, lab in [("Z_서북동계곡", C_VALLEY, "대상: 서북동 계곡(73번 단독 42개)"),
                      ("C_진동환승센터300m", C_JD, "비교: 진동환승센터 반경 300m"),
                      ("H_마산역", INK, "거점: 마산역 반경 300m")]:
    p = allst[allst.spotId.isin(ids(key))]
    ax.scatter(p.xCrdnt, p.yCrdnt, s=22, color=col, edgecolor="white", lw=0.8, zorder=3, label=lab)
for name, dx, dy in [("서북동마을", 0.004, 0.002), ("진동환승센터", 0.004, -0.006), ("마산역종점", 0.004, 0.002)]:
    p = allst[allst.routeName == name].iloc[0]
    ax.annotate(name, (p.xCrdnt, p.yCrdnt), (p.xCrdnt + dx, p.yCrdnt + dy), fontsize=9, color=INK)
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
ax.set_aspect(1 / 0.82)
ax.legend(loc="lower left", fontsize=8, frameon=False)
ax.set_title("그림 1. 분석 대상 위치 (창원 BIS 정류소 좌표, 2026-09-29 조회)", fontsize=10, loc="left")
fig.tight_layout(); fig.savefig(FIG / "fig1_map.png"); plt.close(fig)

# ---- 그림 2: 시간대별 마산역 방향 출발 편수 -----------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4), sharey=True)
for ax, direction, title in [(axes[0], "생활권→마산역", "생활권 → 마산역 (평일)"),
                             (axes[1], "마산역→생활권", "마산역 → 생활권 (평일)")]:
    z = res[(res["구분"].str.startswith("대상")) & (res["방향"] == direction) & (res["요일"] == "평일")].iloc[0]
    c = res[(res["구분"].str.startswith("비교")) & (res["방향"] == direction) & (res["요일"] == "평일")].iloc[0]
    x = range(len(BANDS)); w = 0.38
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], [z[b] for b in BANDS], w, color=C_VALLEY, label="서북동 계곡")
    b2 = ax.bar([i + w / 2 + 0.01 for i in x], [c[b] for b in BANDS], w, color=C_JD, label="진동환승센터 일대")
    for bars in (b1, b2):
        for r in bars:
            ax.annotate(f"{int(r.get_height())}", (r.get_x() + r.get_width() / 2, r.get_height()),
                        ha="center", va="bottom", fontsize=7.5, color="#52514e")
    ax.set_xticks(list(x)); ax.set_xticklabels(BANDS, fontsize=8)
    ax.set_title(title, fontsize=10, loc="left"); ax.grid(axis="y", color="#ecebe7", lw=0.6); ax.set_axisbelow(True)
axes[0].set_ylabel("출발 편수(시각 확인 편)")
axes[0].legend(frameon=False, fontsize=8, loc="upper left")
fig.suptitle("그림 2. 시간대별 버스 출발 편수 — 출발 터미널 공식 시간표 기준", fontsize=10, x=0.01, ha="left")
fig.tight_layout(); fig.savefig(FIG / "fig2_bands.png"); plt.close(fig)

# ---- 그림 3: 시나리오(가정) 출발 기회 --------------------------------------------
opp = pd.read_csv(OUT / "drt_scenario_opportunities.csv", encoding="utf-8-sig")
o = opp[(opp["요일"] == "평일") & (opp["방향"] == "마산역 방향") & (opp["시나리오"] == "S1 07~20시")].iloc[0]
fig, ax = plt.subplots(figsize=(7.6, 3.2))
base = [o[f"{b}_현행"] for b in BANDS]; add = [o[f"{b}_시나리오"] - o[f"{b}_현행"] for b in BANDS]
ax.bar(BANDS, base, 0.55, color=C_VALLEY, label="현행: 73번 직행(관측)")
ax.bar(BANDS, add, 0.55, bottom=[v + 0.08 for v in base], color=C_ADD, hatch="///", edgecolor="white",
       lw=0, label="가정: DRT로 진동환승센터 연결 시 추가로 탈 수 있는 편")
for i, (b, a) in enumerate(zip(base, add)):
    ax.annotate(f"{b + a}", (i, b + a + 0.1), ha="center", va="bottom", fontsize=8, color="#52514e")
ax.set_ylabel("마산역 방향 출발 기회(편)"); ax.grid(axis="y", color="#ecebe7", lw=0.6); ax.set_axisbelow(True)
ax.set_ylim(0, 16); ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
ax.set_title("그림 3. [시나리오·가정] DRT 07~20시 운영 시 계곡 주민의 마산역 방향 출발 기회(평일)", fontsize=10, loc="left")
fig.tight_layout(); fig.savefig(FIG / "fig3_scenario.png"); plt.close(fig)

# ---- 그림 4: 73번 시간대별 탑승(2025-05 1주) ----------------------------------------
h = pd.read_csv(OUT / "boarding_route73_hourly.csv", encoding="utf-8-sig")
h = h[h.total > 0]
fig, ax = plt.subplots(figsize=(7.6, 2.8))
ax.bar(h.hour.str.slice(0, 2), h.total, 0.6, color=MUTED)
ax.set_xlabel("시(탑승 시각)"); ax.set_ylabel("1주 탑승 인원")
ax.grid(axis="y", color="#ecebe7", lw=0.6); ax.set_axisbelow(True)
ax.set_title("그림 4. 73번 노선 전체 시간대별 탑승(2025.5.19~25, 공공데이터포털)", fontsize=10, loc="left")
fig.tight_layout(); fig.savefig(FIG / "fig4_boarding.png"); plt.close(fig)
print("saved", sorted(p.name for p in FIG.glob("*.png")))
