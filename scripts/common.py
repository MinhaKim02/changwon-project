"""공통 로더. 모든 스크립트는 data/raw 원본만 읽고 data/processed에 결과를 쓴다."""
import json
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

BIS_SNAPSHOT = RAW / "cwbis_snapshot_20260929.json"
OFFICIAL_XLSX = RAW / "cw_timetable_20260929.xlsx"
STOPS_CSV = RAW / "datagokr_cw_bus_stops_20251231.csv"

# BIS routeColorCode: 2 간선, 3 지선/읍면, 4 김해시 버스, 5 좌석/급행, 6 기타
GIMHAE_COLOR = "4"


def load_bis():
    return json.loads(BIS_SNAPSHOT.read_text(encoding="utf-8"))


def route_table(snap):
    rl = pd.DataFrame(snap["route_list"])
    bt = pd.DataFrame(snap["bus_time_list"])[["routeId", "routeStle"]]
    df = rl.merge(bt, on="routeId", how="left")
    df["routeId"] = df["routeId"].astype(str)
    return df


def route_stops(snap):
    rows = [r for v in snap["route_stops"].values() for r in v]
    df = pd.DataFrame(rows)
    df["routeId"] = df["routeId"].astype(str)
    return df.sort_values(["routeId", "spotSn"]).reset_index(drop=True)


def timetable(snap):
    """BIS 시간표: 기점(updnSe=0)·종점(updnSe=1) 출발 시각만 제공한다. 중간 정류소 시각은 없다."""
    rows = []
    for key, v in snap["timetables"].items():
        rid, day = key.split("_")
        for r in v or []:
            rows.append({"routeId": rid, "day": int(day), "updnSe": int(r["updnSe"]),
                         "startTime": r["startTime"], "beginDt": r["beginDt"],
                         "rm": r.get("rm")})
    df = pd.DataFrame(rows)
    hm = df["startTime"].str.split(":", expand=True).astype(int)
    df["min"] = hm[0] * 60 + hm[1]
    return df


def load_stops():
    return pd.read_csv(STOPS_CSV, encoding="utf-8-sig")


def official_summary():
    """공식 시간표 xlsx(2026.9.29. 평일기준) '운행계통(전체)' 시트."""
    wb = openpyxl.load_workbook(OFFICIAL_XLSX, read_only=True, data_only=True)
    ws = wb["운행계통(전체)"]
    rows = list(ws.iter_rows(values_only=True))
    out, kind = [], None
    for r in rows[4:]:
        if r[2] is None:
            continue
        kind = r[1] or kind
        t = lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else (str(x) if x else None)
        out.append({"노선종류": str(kind).replace("\n", ""), "노선번호": str(r[2]).strip(),
                    "기점": str(r[3]).replace("\n", " "), "기점_첫차": t(r[4]), "기점_막차": t(r[5]),
                    "종점": str(r[6]).replace("\n", " "), "종점_첫차": t(r[7]), "종점_막차": t(r[8]),
                    "운행대수": r[9], "운행횟수": r[10], "배차간격": r[11]})
    return pd.DataFrame(out)


def norm_route_no(x: str) -> str:
    x = str(x).strip()
    for a, b in [("BRT급행(6000)", "6000"), ("BRT일반(5000)", "5000")]:
        x = x.replace(a, b)
    return x


def split_directions(rs: pd.DataFrame, routes: pd.DataFrame) -> pd.DataFrame:
    """경유 목록(기점→종점→기점 한 줄)을 방향별로 나눈다.
    회차점 = 이름이 종점명과 같은 첫 정류소. 없으면 기점에서 직선거리가 가장 먼 정류소.
    순환 노선(routeStle=2)은 전부 기점 출발편(updnSe 0)."""
    r_by_id = routes.set_index("routeId") if "routeId" in routes.columns else routes
    out = []
    for rid, g in rs.groupby("routeId"):
        g = g.sort_values("spotSn").reset_index(drop=True)
        r = r_by_id.loc[rid]
        if str(r.routeStle) == "2":
            g["updnSe"], g["split_rule"] = 0, "순환"
        else:
            end = str(r.endRoute).replace(" ", "")
            hit = [i for i in range(1, len(g)) if g.routeName[i].replace(" ", "") == end]
            if hit:
                k, how = hit[0], "종점명 일치"
            else:
                d = np.hypot((g.xCrdnt - g.xCrdnt[0]) * np.cos(np.radians(35.2)), g.yCrdnt - g.yCrdnt[0])
                k, how = int(d.argmax()), "최원거리"
            g["updnSe"] = [0 if i < k else 1 for i in range(len(g))]
            g["split_rule"] = how
        out.append(g)
    return pd.concat(out, ignore_index=True)
