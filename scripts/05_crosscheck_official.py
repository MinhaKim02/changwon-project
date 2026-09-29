"""결과표에 쓴 노선의 BIS 시간표를 창원시 공식 시간표 xlsx(2026.9.29. 기준, 읍면노선 시트)와 편별로 대조한다.

방법: 해당 노선 블록(헤더 '노선번호' 다음 행들)의 평일 영역에서 기점·종점 출발 열의 시각을 모두 모아
BIS 평일 기점(updnSe 0)·종점(updnSe 1) 출발 시각 집합과 비교한다. 블록 오른쪽에 '토,일요일' 표가 있으면
그것을 BIS 일·공휴일 시간표와 비교한다.
출력: data/processed/crosscheck_official.csv
"""
import openpyxl
import pandas as pd

from common import OFFICIAL_XLSX, OUT, load_bis, route_table, timetable

# 노선: (평일 기점 열 이름, 평일 종점 열 이름) — 공식 xlsx 블록 헤더 그대로
TARGETS = {"73": ("마산역", "서북동"), "80": ("진동", "마산역")}

snap = load_bis()
routes = route_table(snap)
tt = timetable(snap)
wb = openpyxl.load_workbook(OFFICIAL_XLSX, read_only=True, data_only=True)
rows = list(wb["읍면노선"].iter_rows(values_only=True))
fmt = lambda c: c.strftime("%H:%M") if hasattr(c, "strftime") else None

out = []
for no, (col_a, col_b) in TARGETS.items():
    h = next(i for i, r in enumerate(rows) if r[0] == "노선번호" and i + 1 < len(rows)
             and str(rows[i + 1][0]).strip() == no)
    header = [str(c).strip() if c is not None else "" for c in rows[h]]
    second = next((j for j in range(1, len(header)) if header[j] == "노선번호"), len(header))
    body = []
    for r in rows[h + 1:]:
        if r[0] is None or str(r[0]).strip() != no:
            break
        body.append(r)

    def col_times(name, start, end):
        idx = [j for j in range(start, end) if header[j] == name]
        return sorted(t for r in body for j in idx[:1] for t in [fmt(r[j])] if t)

    parts = [("평일", 1, 0, second)]
    if second < len(header):
        parts.append(("토·일(공식) vs 일·공휴일(BIS)", 3, second, len(header)))
    rid = routes.loc[routes.routeNo == no, "routeId"].iloc[0]
    for label, day, s, e in parts:
        for ud, name in [(0, col_a), (1, col_b)]:
            off = col_times(name, s, e)
            bis = sorted(tt[(tt.routeId == rid) & (tt.day == day) & (tt.updnSe == ud)].startTime)
            out.append({"노선": no, "요일": label, "방향": "기점 출발" if ud == 0 else "종점 출발",
                        "공식 열": name, "공식 편수": len(off), "BIS 편수": len(bis),
                        "완전 일치": off == bis,
                        "공식에만": " ".join(sorted(set(off) - set(bis))),
                        "BIS에만": " ".join(sorted(set(bis) - set(off)))})

df = pd.DataFrame(out)
df.to_csv(OUT / "crosscheck_official.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))
