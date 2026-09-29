"""3단계-2: 결과표 1 — 생활권·비교 대상과 목적 거점(마산역) 사이의 요일·시간대별 버스 출발 선택지.

원칙
- 시각은 노선의 '출발 터미널(기점 또는 종점)'에서의 공식 시간표 출발 시각만 사용한다.
- 출발지가 해당 편의 출발 터미널이 아니면(중간 경유), 그 편은 하루 편수에는 넣되 시간대 칸에는 넣지 않는다
  ('시각 미산출' 열). 첫차·막차·배차간격으로 중간 정류소 시각을 추정하지 않는다.
- 요일: 평일(BIS 2026-09-28 적용 시간표), 일요일·공휴일(BIS 2026-10-03 적용 시간표).
  토요일은 BIS가 조회 시점에 빈 결과를 돌려줘 이 표에서 제외한다(공식 xlsx로 별도 확인 필요).

정의(재현 가능한 규칙)
- 거점 H(마산역): '마산역종점'(379000725) 반경 300m(직선) 안의 정류소.
- 대상 생활권 Z(진북면 서북동 계곡): 평일에 73번 한 노선만 정차하는 정류소 전체.
- 비교 대상 C(진동): '진동환승센터'(379005359) 반경 300m(직선) 안의 정류소.

출력: data/processed/result_table_1_long.csv, result_table_1.csv, result_table_1.md, dashboard/data.json 일부
"""
import json

import numpy as np
import pandas as pd

from common import GIMHAE_COLOR, OUT, load_bis, route_stops, route_table, split_directions, timetable

BANDS = [(0, 7, "~07시"), (7, 9, "07–09시"), (9, 12, "09–12시"), (12, 15, "12–15시"),
         (15, 18, "15–18시"), (18, 20, "18–20시"), (20, 24, "20시~")]
DAYS = {1: "평일", 3: "일·공휴일"}

snap = load_bis()
routes = route_table(snap)
routes = routes[routes.routeColorCode != GIMHAE_COLOR].set_index("routeId")
rs = route_stops(snap)
rs = rs[rs.routeId.isin(routes.index)].copy()
tt = timetable(snap)


rs = split_directions(rs, routes.reset_index())

# ---- 지점 정의 ---------------------------------------------------------------
RADIUS_M = 300


def within(spot_id: int, radius=RADIUS_M) -> set:
    u = rs.drop_duplicates("spotId")
    c = u[u.spotId == spot_id].iloc[0]
    d = np.hypot((u.xCrdnt - c.xCrdnt) * 111320 * np.cos(np.radians(35.2)), (u.yCrdnt - c.yCrdnt) * 110540)
    return set(u.loc[d <= radius, "spotId"])


H = within(379000725)
wk_routes_by_stop = rs.merge(tt[tt.day == 1][["routeId"]].drop_duplicates(), on="routeId") \
                      .groupby("spotId").routeId.agg(lambda s: frozenset(s))
r73 = set(routes.index[routes.routeNo == "73"])
Z = {s for s, rset in wk_routes_by_stop.items() if rset and rset <= r73}
C = within(379005359)
places = {"대상: 진북면 서북동 계곡(73번 단독 정차 정류소)": Z, "비교: 진동환승센터 일대(반경 300m)": C}


def trips_between(origin: set, dest: set):
    """origin→dest 로 가는 (노선, 방향)과 origin에서의 출발 시각 산출 가능 여부."""
    out = []
    for (rid, ud), g in rs.groupby(["routeId", "updnSe"]):
        g = g.sort_values("spotSn")
        o = g.index[g.spotId.isin(origin)]
        d = g.index[g.spotId.isin(dest)]
        if len(o) and len(d) and o.min() < d.max():
            first_stop = g.spotId.iloc[0]
            out.append({"routeId": rid, "updnSe": ud, "routeNo": routes.loc[rid, "routeNo"],
                        "time_known_at_origin": first_stop in origin,
                        "origin_terminal": g.routeName.iloc[0]})
    return pd.DataFrame(out)


rows, route_rows = [], []
for pname, pset in places.items():
    for direction, (o, d) in {"생활권→마산역": (pset, H), "마산역→생활권": (H, pset)}.items():
        legs = trips_between(o, d)
        legs["place"], legs["direction"] = pname, direction
        route_rows.append(legs)
        for day, dname in DAYS.items():
            x = tt[tt.day == day].merge(legs, on=["routeId", "updnSe"])
            known = x[x.time_known_at_origin]
            rec = {"구분": pname, "방향": direction, "요일": dname,
                   "시각 기준": "출발 터미널 시간표",
                   "기준일": ",".join(sorted(x.beginDt.unique()))}
            for a, b, lab in BANDS:
                rec[lab] = int(((known["min"] >= a * 60) & (known["min"] < b * 60)).sum())
            rec["시각 산출 편수"] = int(len(known))
            rec["첫 출발"] = known.startTime.min() if len(known) else "-"
            rec["마지막 출발"] = known.startTime.max() if len(known) else "-"
            rec["시각 미산출(중간경유) 편수"] = int((~x.time_known_at_origin).sum())
            rec["노선(시각 산출)"] = ", ".join(sorted(known.routeNo.unique(), key=str))
            rec["노선(중간경유)"] = ", ".join(sorted(x.loc[~x.time_known_at_origin, "routeNo"].unique(), key=str))
            rows.append(rec)

res = pd.DataFrame(rows)
res.to_csv(OUT / "result_table_1.csv", index=False, encoding="utf-8-sig")
legs_all = pd.concat(route_rows, ignore_index=True)
legs_all.to_csv(OUT / "result_table_1_legs.csv", index=False, encoding="utf-8-sig")

# 편별 원자료(재현·검증용): 어떤 노선의 몇 시 출발이 어느 칸에 들어갔는지
long = []
for _, lg in legs_all.iterrows():
    for day, dname in DAYS.items():
        x = tt[(tt.routeId == lg.routeId) & (tt.updnSe == lg.updnSe) & (tt.day == day)]
        for _, t in x.iterrows():
            band = next((lab for a, b, lab in BANDS if a * 60 <= t["min"] < b * 60), None)
            long.append({"구분": lg.place, "방향": lg.direction, "요일": dname, "노선": lg.routeNo,
                         "routeId": lg.routeId, "updnSe": lg.updnSe, "출발 터미널": lg.origin_terminal,
                         "출발시각": t.startTime, "시간대": band if lg.time_known_at_origin else "시각 미산출(중간경유)",
                         "기준일": t.beginDt})
pd.DataFrame(long).to_csv(OUT / "result_table_1_long.csv", index=False, encoding="utf-8-sig")

# 지점 정의 기록
stop_names = rs.drop_duplicates("spotId").set_index("spotId")
defs = {k: sorted({f"{stop_names.loc[s, 'routeName']}({s})" for s in v}) for k, v in
        {"H_마산역": H, "Z_서북동계곡": Z, "C_진동환승센터300m": C}.items()}
(OUT / "result_table_1_place_definitions.json").write_text(json.dumps(defs, ensure_ascii=False, indent=2), encoding="utf-8")

cols = ["구분", "방향", "요일"] + [b[2] for b in BANDS] + ["시각 산출 편수", "첫 출발", "마지막 출발",
                                                          "시각 미산출(중간경유) 편수", "노선(시각 산출)", "노선(중간경유)"]
(OUT / "result_table_1.md").write_text(res[cols].to_markdown(index=False), encoding="utf-8")
print(res[cols].to_string(index=False))
print({k: len(v) for k, v in defs.items()})
