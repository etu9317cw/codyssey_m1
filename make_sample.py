"""시뮬레이션 데이터 생성기 — 센터 교육동 일별 전력 사용량 (kWh)

실데이터를 확보하기 전까지 분석 파이프라인을 검증하기 위한 **가상 데이터**다.
생성 규칙은 data/README.md 와 이 파일의 RULES 에 그대로 적혀 있으며, 시드를 고정해 누구나 같은 파일을 다시 만들 수 있다.

사용:  python make_sample.py  [--start 2024-10-01] [--days 730] [--seed 260000] [--out data/sample/electricity_daily.csv]
출력:  date,value,temp_c,is_holiday,memo   (value = kWh, temp_c = 일평균 기온 ℃)
"""
import argparse
import csv
import math
import random
from datetime import date, timedelta

# ---------- 생성 규칙 (리포트 3장·data/README.md 와 동일하게 유지) ----------
RULES = {
    "base_kwh": 1800.0,          # 평일·학기 외 기본 사용량
    "semester_factor": 1.25,     # 학기 중(3~6월, 9~12월) ×1.25
    "vacation_factor": 0.80,     # 방학(1~2월, 7~8월) ×0.80
    "weekend_factor": 0.55,      # 토·일 ×0.55
    "holiday_factor": 0.50,      # 공휴일 ×0.50
    "cooling_threshold_c": 26.0, # 이 기온 초과 시 1℃당 +1.5%
    "heating_threshold_c": 5.0,  # 이 기온 미만 시 1℃당 +1.5%
    "hvac_pct_per_deg": 0.015,
    "noise_sd": 0.04,            # 정규 노이즈 표준편차 4%
    "trend_per_year": 0.03,      # 연 3% 완만한 증가(장비 증설 가정)
    "outlier_count": 6,          # 이상치(정전·행사) 6일
}

# 고정 공휴일 목록(간략). 음력 명절은 해당 연도 날짜를 직접 적었다.
HOLIDAYS = {
    # 2024
    "2024-10-03": "개천절", "2024-10-09": "한글날", "2024-12-25": "성탄절",
    # 2025
    "2025-01-01": "신정", "2025-01-28": "설 연휴", "2025-01-29": "설날", "2025-01-30": "설 연휴",
    "2025-03-01": "삼일절", "2025-03-03": "대체공휴일", "2025-05-05": "어린이날·부처님오신날", "2025-05-06": "대체공휴일",
    "2025-06-03": "대통령선거", "2025-06-06": "현충일", "2025-08-15": "광복절",
    "2025-10-03": "개천절", "2025-10-05": "추석 연휴", "2025-10-06": "추석", "2025-10-07": "추석 연휴", "2025-10-08": "대체공휴일",
    "2025-10-09": "한글날", "2025-12-25": "성탄절",
    # 2026
    "2026-01-01": "신정", "2026-02-16": "설 연휴", "2026-02-17": "설날", "2026-02-18": "설 연휴",
    "2026-03-01": "삼일절", "2026-03-02": "대체공휴일", "2026-05-05": "어린이날", "2026-05-24": "부처님오신날", "2026-05-25": "대체공휴일",
    "2026-06-03": "지방선거", "2026-06-06": "현충일", "2026-08-15": "광복절", "2026-08-17": "대체공휴일",
    "2026-09-24": "추석 연휴", "2026-09-25": "추석", "2026-09-26": "추석 연휴",
}

SEMESTER_MONTHS = {3, 4, 5, 6, 9, 10, 11, 12}


def daily_temperature(d: date, rng: random.Random) -> float:
    """연중 기온 모델: 평균 13.5℃, 진폭 13℃(1월 말 최저, 7월 말 최고) + 노이즈 ±3℃."""
    day_of_year = d.timetuple().tm_yday
    seasonal = 13.5 - 13.0 * math.cos(2 * math.pi * (day_of_year - 28) / 365.25)
    return round(seasonal + rng.gauss(0, 3.0), 1)


def hvac_factor(temp_c: float) -> float:
    """냉난방 가중치: 26℃ 초과·5℃ 미만 구간에서 1℃당 +1.5%."""
    extra = 0.0
    if temp_c > RULES["cooling_threshold_c"]:
        extra = (temp_c - RULES["cooling_threshold_c"]) * RULES["hvac_pct_per_deg"]
    elif temp_c < RULES["heating_threshold_c"]:
        extra = (RULES["heating_threshold_c"] - temp_c) * RULES["hvac_pct_per_deg"]
    return 1.0 + extra


def generate(start: date, days: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        key = d.isoformat()
        temp = daily_temperature(d, rng)
        value = RULES["base_kwh"]
        memo = []

        # 학기/방학
        if d.month in SEMESTER_MONTHS:
            value *= RULES["semester_factor"]
            memo.append("학기")
        else:
            value *= RULES["vacation_factor"]
            memo.append("방학")

        # 주말·공휴일
        is_holiday = key in HOLIDAYS
        if is_holiday:
            value *= RULES["holiday_factor"]
            memo.append(HOLIDAYS[key])
        elif d.weekday() >= 5:
            value *= RULES["weekend_factor"]
            memo.append("주말")

        # 냉난방·추세·노이즈
        value *= hvac_factor(temp)
        value *= 1.0 + RULES["trend_per_year"] * (i / 365.25)
        value *= 1.0 + rng.gauss(0, RULES["noise_sd"])

        rows.append({"date": key, "value": round(value, 1), "temp_c": temp,
                     "is_holiday": int(is_holiday), "memo": " ".join(memo)})

    # 이상치: 정전(급감)·대형 행사(급증)를 평일에 심는다
    weekday_idx = [i for i, r in enumerate(rows) if "주말" not in r["memo"] and not r["is_holiday"]]
    chosen = rng.sample(weekday_idx, RULES["outlier_count"])
    for n, idx in enumerate(sorted(chosen)):
        if n % 2 == 0:
            rows[idx]["value"] = round(rows[idx]["value"] * 0.35, 1)
            rows[idx]["memo"] += " 정전·점검(이상치)"
        else:
            rows[idx]["value"] = round(rows[idx]["value"] * 1.60, 1)
            rows[idx]["memo"] += " 대형행사(이상치)"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2024-10-01")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--seed", type=int, default=260000)
    parser.add_argument("--out", default="data/sample/electricity_daily.csv")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    rows = generate(start, args.days, args.seed)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "temp_c", "is_holiday", "memo"])
        writer.writeheader()
        writer.writerows(rows)
    values = [r["value"] for r in rows]
    print(f"{args.out}: {len(rows)}행, {rows[0]['date']} ~ {rows[-1]['date']}, "
          f"평균 {sum(values)/len(values):,.1f} kWh, 최소 {min(values):,.1f}, 최대 {max(values):,.1f}, seed={args.seed}")


if __name__ == "__main__":
    main()
