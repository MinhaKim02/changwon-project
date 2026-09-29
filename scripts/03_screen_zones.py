"""3단계-1: 생활권 후보 선별(스크리닝).

정류소별로 '그 정류소를 지나는 노선의 하루 출발 편수'를 센다.
- 시간표는 기점·종점 출발 시각뿐이므로, 여기서는 '하루 몇 편이 그 정류소를 지나가는가'(시각 무관)만 계산한다.
- 방향 구분: common.split_directions (종점명과 같은 첫 정류소를 회차점으로, 없으면 최원거리 정류소).
- 행정구역은 공공데이터포털 정류소 파일의 '동코드'(실제 값은 읍면동 이름) 열을 쓴다. 결측 정류소는 '미상'.

출력: data/processed/stop_service_weekday.csv, data/processed/zone_screen.csv
"""
import numpy as np
import pandas as pd

from common import (GIMHAE_COLOR, OUT, load_bis, load_stops, route_stops, route_table,
                    split_directions, timetable)

snap = load_bis()
routes = route_table(snap)
routes = routes[routes.routeColorCode != GIMHAE_COLOR]
rs = route_stops(snap)
rs = rs[rs.routeId.isin(routes.routeId)].copy()
tt = timetable(snap)
stops = load_stops()


rs = split_directions(rs, routes)
rs.to_csv(OUT / "route_stops_directed.csv", index=False, encoding="utf-8-sig")

dep = tt.groupby(["routeId", "day", "updnSe"]).size().rename("departures").reset_index()
svc = rs.drop_duplicates(["routeId", "updnSe", "spotId"]).merge(dep, on=["routeId", "updnSe"])
per_stop = (svc.pivot_table(index="spotId", columns="day", values="departures", aggfunc="sum", fill_value=0)
               .rename(columns={1: "weekday_trips", 3: "holiday_trips"}))
per_stop["routes"] = svc[svc.day == 1].groupby("spotId").routeId.nunique()
per_stop = per_stop.reset_index().merge(
    stops[["정류소아이디", "정류소명", "동코드", "경도", "위도"]].rename(columns={"정류소아이디": "spotId"}),
    on="spotId", how="left")
per_stop["동코드"] = per_stop["동코드"].fillna("미상")
per_stop.to_csv(OUT / "stop_service_weekday.csv", index=False, encoding="utf-8-sig")

zone = (per_stop.groupby("동코드")
          .agg(stops=("spotId", "size"),
               median_weekday_trips=("weekday_trips", "median"),
               p25_weekday_trips=("weekday_trips", lambda s: s.quantile(.25)),
               stops_under_10_weekday=("weekday_trips", lambda s: int((s < 10).sum())),
               median_holiday_trips=("holiday_trips", "median"))
          .reset_index().sort_values("median_weekday_trips"))
zone.to_csv(OUT / "zone_screen.csv", index=False, encoding="utf-8-sig")
print(zone.head(25).to_string(index=False))
print("...")
print(zone.tail(8).to_string(index=False))
