"""2단계: 노선-정류소 연결과 시간표 현행성 검증.

출력
- data/processed/validation_stop_link.csv   : 노선별 경유정류소 ↔ 공공데이터포털 정류소 ID 연결률
- data/processed/validation_timetable.csv   : BIS 평일 시간표 ↔ 공식 xlsx(2026.9.29.) 첫차·막차 대조
- data/processed/validation_summary.json    : 요약 수치
"""
import json
import re

import numpy as np
import pandas as pd

from common import (GIMHAE_COLOR, OUT, load_bis, load_stops, norm_route_no,
                    official_summary, route_stops, route_table, timetable)

snap = load_bis()
routes = route_table(snap)
rs = route_stops(snap)
tt = timetable(snap)
stops = load_stops()
off = official_summary()

cw_routes = routes[routes.routeColorCode != GIMHAE_COLOR].copy()
summary = {"bis_retrieved_at": snap["retrieved_at"],
           "bis_routes_total": int(len(routes)),
           "bis_routes_changwon": int(len(cw_routes)),
           "bis_routes_gimhae_excluded": int((routes.routeColorCode == GIMHAE_COLOR).sum())}

# ---- A. 정류소 연결 ---------------------------------------------------------
rs_cw = rs[rs.routeId.isin(cw_routes.routeId)].copy()
st = stops.rename(columns={"정류소아이디": "spotId", "서비스아이디": "svc_datagokr",
                           "경도": "lon_d", "위도": "lat_d", "정류소명": "name_d"})
m = rs_cw.merge(st[["spotId", "svc_datagokr", "name_d", "lon_d", "lat_d", "동코드"]],
                on="spotId", how="left")
m["linked"] = m["lon_d"].notna()
# 연결된 정류소의 좌표 차이(m) — 같은 정류소인지 검사
lat0 = np.radians(35.2)
dx = (m.xCrdnt - m.lon_d) * 111320 * np.cos(lat0)
dy = (m.yCrdnt - m.lat_d) * 110540
m["coord_diff_m"] = np.sqrt(dx ** 2 + dy ** 2)
m["name_same"] = m.routeName.str.replace(" ", "") == m.name_d.fillna("").str.replace(" ", "")
m["svc_same"] = m.sttnSrvcId.astype(str) == m.svc_datagokr.astype("Int64").astype(str)

per_route = (m.groupby(["routeId", "routeNo"])
               .agg(stops=("spotId", "size"), linked=("linked", "sum"),
                    unlinked_names=("routeName", lambda s: ", ".join(sorted(set(s[~m.loc[s.index, "linked"]]))[:8])))
               .reset_index())
per_route["link_rate"] = (per_route.linked / per_route.stops).round(4)
per_route.sort_values("link_rate").to_csv(OUT / "validation_stop_link.csv", index=False, encoding="utf-8-sig")

lk = m[m.linked]
summary.update({
    "route_stop_rows": int(len(m)),
    "route_stop_rows_linked": int(m.linked.sum()),
    "route_stop_link_rate": round(float(m.linked.mean()), 4),
    "unique_stops_on_routes": int(m.spotId.nunique()),
    "unique_stops_unlinked": int(m.loc[~m.linked, "spotId"].nunique()),
    "linked_coord_diff_m_median": round(float(lk.coord_diff_m.median()), 1),
    "linked_coord_diff_m_p95": round(float(lk.coord_diff_m.quantile(.95)), 1),
    "linked_coord_diff_over_50m": int((lk.coord_diff_m > 50).sum()),
    "linked_name_same_rate": round(float(lk.name_same.mean()), 4),
    "linked_serviceid_same_rate": round(float(lk.svc_same.mean()), 4),
    "routes_with_all_stops_linked": int((per_route.link_rate == 1).sum()),
    "routes_total_checked": int(len(per_route)),
})

# ---- B/C. 시간표 현행성: BIS 평일 ↔ 공식 xlsx 첫차·막차 --------------------
wk = tt[tt.day == 1]
agg = (wk.groupby(["routeId", "updnSe"])
         .agg(first=("min", "min"), last=("min", "max"), n=("min", "size"), beginDt=("beginDt", "first"))
         .reset_index())
fmt = lambda v: f"{int(v)//60:02d}:{int(v)%60:02d}"
agg["first"] = agg["first"].map(fmt)
agg["last"] = agg["last"].map(fmt)
piv = agg.pivot(index="routeId", columns="updnSe", values=["first", "last", "n"])
piv.columns = [f"bis_{a}_{'기점' if b == 0 else '종점'}" for a, b in piv.columns]
piv = piv.reset_index().merge(cw_routes[["routeId", "routeNo", "startRoute", "endRoute"]], on="routeId")
piv["key"] = piv.routeNo.map(norm_route_no)
off["key"] = off["노선번호"].map(norm_route_no)
cmp = off.merge(piv, on="key", how="outer", indicator=True)


def same(a, b):
    return (a == b) if isinstance(a, str) and isinstance(b, str) else np.nan


cmp["기점첫차_일치"] = [same(a, b) for a, b in zip(cmp["기점_첫차"], cmp["bis_first_기점"])]
cmp["기점막차_일치"] = [same(a, b) for a, b in zip(cmp["기점_막차"], cmp["bis_last_기점"])]
cmp.to_csv(OUT / "validation_timetable.csv", index=False, encoding="utf-8-sig")

# 방향 표기(기점/종점)가 두 자료에서 뒤바뀐 노선, 한 번호에 여러 routeId(분리 운행)가 있는 노선을
# 고려해 '노선번호 단위, 양방향 합산' 첫차·막차 집합으로 다시 대조한다.
wk_no = wk.merge(cw_routes[["routeId", "routeNo"]], on="routeId")
wk_no["key"] = wk_no.routeNo.map(norm_route_no)
by_no = wk_no.groupby("key")["min"].agg(["min", "max"]).map(fmt)
off_first = off.set_index("key")[["기점_첫차", "종점_첫차"]].min(axis=1)
off_last = off.set_index("key")[["기점_막차", "종점_막차"]].max(axis=1)
# 변형 노선(예: 510-1)은 공식 요약표에서 본 번호에 합쳐져 있으므로 본 번호 기준으로 합친다.
offkeys = set(off.key)
wk_no["base"] = [k if k in offkeys else re.sub(r"-\d+$", "", k) for k in wk_no.key]
by_base = wk_no.groupby("base")["min"].agg(["min", "max"]).map(fmt)
rows = []
for k in off.key:
    b = by_base.loc[k] if k in by_base.index else None
    rows.append({"노선": k, "공식_첫차(양방향)": off_first[k], "BIS_첫차": b["min"] if b is not None else None,
                 "공식_막차(양방향)": off_last[k], "BIS_막차": b["max"] if b is not None else None})
cmp2 = pd.DataFrame(rows)
cmp2["첫차_일치"] = cmp2["공식_첫차(양방향)"] == cmp2["BIS_첫차"]
cmp2["막차_일치"] = cmp2["공식_막차(양방향)"] == cmp2["BIS_막차"]
cmp2.to_csv(OUT / "validation_timetable_by_route.csv", index=False, encoding="utf-8-sig")
summary.update({
    "route_level_first_match_rate": round(float(cmp2["첫차_일치"].mean()), 4),
    "route_level_last_match_rate": round(float(cmp2["막차_일치"].mean()), 4),
    "route_level_mismatch_routes": cmp2.loc[~(cmp2["첫차_일치"] & cmp2["막차_일치"]), "노선"].tolist(),
})

both = cmp[cmp._merge == "both"]
summary.update({
    "official_routes_in_xlsx": int(len(off)),
    "official_routes_matched_to_bis": int(both.key.nunique()),
    "official_routes_not_in_bis": sorted(cmp.loc[cmp._merge == "left_only", "key"].unique().tolist()),
    "bis_routes_not_in_official": sorted(cmp.loc[cmp._merge == "right_only", "key"].unique().tolist()),
    "first_departure_match_rate": round(float(both["기점첫차_일치"].dropna().mean()), 4),
    "last_departure_match_rate": round(float(both["기점막차_일치"].dropna().mean()), 4),
    "bis_timetable_beginDt": sorted(tt.groupby("day").beginDt.unique().map(list).to_dict().items()),
    "bis_saturday_rows": int((tt.day == 2).sum()),
})

# ---- D. 2026 변경 공지 반영 여부(키워드 검사) -----------------------------
names = rs.groupby("routeNo").routeName.apply(lambda s: " ".join(s))
checks = {"19번 최윤덕도서관 경유(2026.9.24.)": ("19", "최윤덕도서관"),
          "80번 감천 운행(2026.9.24.)": ("80", "감천"),
          "351번 대장동계곡 연장(2026.9.24.)": ("351", "대장동"),
          "214번 사화롯데캐슬 경유(2026.9.24.)": ("214", "롯데캐슬")}
summary["notice_checks"] = {k: bool(n in names.index and kw in names[n]) for k, (n, kw) in checks.items()}
summary["route_219_present_in_bis"] = bool((routes.routeNo == "219").any())

(OUT / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
