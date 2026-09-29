"""5단계: 정적 대시보드. 보고서와 같은 data/processed 결과를 읽어 dashboard/index.html 하나로 만든다(데이터 내장, 서버 불필요).
"""
import json

import pandas as pd

from common import OUT, ROOT, load_bis, route_stops

res = pd.read_csv(OUT / "result_table_1.csv", encoding="utf-8-sig")
opp = pd.read_csv(OUT / "drt_scenario_opportunities.csv", encoding="utf-8-sig")
val = json.loads((OUT / "validation_summary.json").read_text(encoding="utf-8"))
drt = json.loads((OUT / "drt_scenario_summary.json").read_text(encoding="utf-8"))
defs = json.loads((OUT / "result_table_1_place_definitions.json").read_text(encoding="utf-8"))
BANDS = ["~07시", "07–09시", "09–12시", "12–15시", "15–18시", "18–20시", "20시~"]

rs = route_stops(load_bis())
ids = lambda k: {int(x.split("(")[1].rstrip(")")) for x in defs[k]}
u = rs.drop_duplicates("spotId")
box = u[u.xCrdnt.between(128.36, 128.62) & u.yCrdnt.between(35.08, 35.27)]
r73 = rs[rs.routeId == "379000730"].sort_values("spotSn")
geo = {"bg": box[["xCrdnt", "yCrdnt"]].round(5).values.tolist(),
       "route": r73[["xCrdnt", "yCrdnt"]].round(5).values.tolist(),
       "Z": u[u.spotId.isin(ids("Z_서북동계곡"))][["xCrdnt", "yCrdnt"]].round(5).values.tolist(),
       "C": u[u.spotId.isin(ids("C_진동환승센터300m"))][["xCrdnt", "yCrdnt"]].round(5).values.tolist(),
       "H": u[u.spotId.isin(ids("H_마산역"))][["xCrdnt", "yCrdnt"]].round(5).values.tolist()}

data = {
    "bands": BANDS,
    "result": [{"place": "서북동 계곡" if r["구분"].startswith("대상") else "진동환승센터 일대",
                "dir": r["방향"], "day": r["요일"], "counts": [int(r[b]) for b in BANDS],
                "total": int(r["시각 산출 편수"]), "first": r["첫 출발"], "last": r["마지막 출발"],
                "through": int(r["시각 미산출(중간경유) 편수"]),
                "routes": r["노선(시각 산출)"]} for _, r in res.iterrows()],
    "scenario": [{"day": r["요일"], "dir": r["방향"], "scen": r["시나리오"],
                  "base": [int(r[f"{b}_현행"]) for b in BANDS], "with": [int(r[f"{b}_시나리오"]) for b in BANDS]}
                 for _, r in opp.iterrows()],
    "facts": {"link_rate": val["route_stop_link_rate"], "retrieved": "2026-09-29",
              "boarding_week": drt["valley_weekly_boardings_unique_names"],
              "dist_first": f"{drt['dist_km_jindong_to_first_valley_stop']:.1f}", "dist_last": drt["dist_km_jindong_to_seobukdong_terminal"]},
    "geo": geo,
}

tpl = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
(ROOT / "dashboard" / "index.html").write_text(tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
print("dashboard/index.html written")
