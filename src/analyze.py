"""시계열 분석 기법 4가지 + 이상치 표시 + 구간 통계.

1. 이동평균(7일·30일)            → 추세
2. 변화율(전일·전주 대비 %)       → 급변 지점
3. 월별·요일별 집계              → 계절성·주간 패턴
4. 30일 이동 표준편차(변동성)     → 안정/불안정 구간
+ 이상치: 같은 요일 평균 대비 ±30% 벗어나면 표시(제거하지 않음)
+ 학기/방학 구간 통계, 기온 상관(temp_c가 있을 때)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
SEMESTER_MONTHS = {3, 4, 5, 6, 9, 10, 11, 12}
OUTLIER_PCT = 0.30
TREND_BAND = 0.05  # 최근 7일 vs 이전 7일 평균 차이가 ±5% 안이면 '유지'


def add_moving_averages(df: pd.DataFrame, windows=(7, 30)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"ma{w}"] = df["value"].rolling(w, min_periods=max(1, w // 2)).mean()
    return df


def add_change_rates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["pct_change_1d"] = df["value"].pct_change(1) * 100
    df["pct_change_7d"] = df["value"].pct_change(7) * 100
    return df


def add_volatility(df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    df = df.copy()
    df[f"std{window}"] = df["value"].rolling(window, min_periods=window // 2).std()
    return df


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["weekday"] = df["date"].dt.weekday
    df["weekday_ko"] = df["weekday"].map(lambda i: WEEKDAY_KO[i])
    df["period"] = np.where(df["month"].isin(SEMESTER_MONTHS), "학기", "방학")
    if "is_holiday" not in df:
        df["is_holiday"] = 0
    df["day_type"] = np.select(
        [df["is_holiday"] == 1, df["weekday"] >= 5],
        ["공휴일", "주말"], default="평일")
    return df


def flag_outliers(df: pd.DataFrame, pct: float = OUTLIER_PCT, min_group: int = 4) -> pd.DataFrame:
    """기준값(같은 구간·같은 날 유형·같은 요일의 평균) 대비 ±pct 벗어나면 outlier=True. 값은 바꾸지 않는다.

    구간(학기/방학)과 날 유형(평일/주말/공휴일)을 나누지 않으면 방학·공휴일이 전부 이상치로 잡히므로
    (학기, 평일, 월요일)처럼 같은 조건끼리 비교한다. 그룹이 min_group보다 작으면(공휴일 등) (구간, 날 유형) 평균을 쓴다.
    """
    df = df.copy()
    fine = df.groupby(["period", "day_type", "weekday"])["value"]
    coarse = df.groupby(["period", "day_type"])["value"]
    ref = fine.transform("mean").where(fine.transform("count") >= min_group, coarse.transform("mean"))
    df["weekday_mean"] = ref
    df["dev_from_weekday_mean"] = (df["value"] - ref) / ref * 100
    df["outlier"] = df["dev_from_weekday_mean"].abs() > pct * 100
    df["outlier_direction"] = np.select(
        [df["outlier"] & (df["dev_from_weekday_mean"] > 0), df["outlier"]],
        ["급증", "급감"], default="")
    return df


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby([df["date"].dt.to_period("M")])["value"]
    out = pd.DataFrame({"mean": g.mean(), "sum": g.sum(), "max": g.max(), "min": g.min(), "days": g.count()})
    out.index = out.index.astype(str)
    out.index.name = "month"
    return out.round(1)


def weekday_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("weekday")["value"]
    out = pd.DataFrame({"mean": g.mean(), "std": g.std(), "days": g.count()})
    out.insert(0, "weekday_ko", [WEEKDAY_KO[i] for i in out.index])
    weekday_avg = out.loc[out.index < 5, "mean"].mean()
    out["vs_weekday_pct"] = (out["mean"] / weekday_avg - 1) * 100
    return out.round(1)


def period_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["period", "day_type"])["value"]
    out = pd.DataFrame({"mean": g.mean(), "days": g.count()})
    return out.round(1)


def temperature_correlation(df: pd.DataFrame) -> dict | None:
    """기온과 사용량의 피어슨 상관. 평일만, 냉방(>26)·난방(<5)·중간 구간 평균도 함께."""
    if "temp_c" not in df or df["temp_c"].isna().all():
        return None
    weekday = df[(df["day_type"] == "평일") & df["value"].notna() & df["temp_c"].notna()]
    if len(weekday) < 30:
        return None
    def _bands(frame: pd.DataFrame) -> dict:
        bins = {
            "난방(5℃ 미만)": frame[frame["temp_c"] < 5]["value"].mean(),
            "중간(5~26℃)": frame[(frame["temp_c"] >= 5) & (frame["temp_c"] <= 26)]["value"].mean(),
            "냉방(26℃ 초과)": frame[frame["temp_c"] > 26]["value"].mean(),
        }
        return {k: (round(float(v), 1) if pd.notna(v) else None) for k, v in bins.items()}

    r_all = float(weekday["value"].corr(weekday["temp_c"]))
    # 기온 절대 편차(18℃ 기준)와의 상관: 냉난방 둘 다 올라가는 U자형을 잡기 위해
    dev = (weekday["temp_c"] - 18).abs()
    r_dev = float(weekday["value"].corr(dev))
    # 여름(냉방 구간)은 대부분 방학이라 전체 평일로 보면 냉방 효과가 가려진다 → 구간별로 나눠서도 본다
    semester = weekday[weekday["period"] == "학기"]
    vacation = weekday[weekday["period"] == "방학"]
    out = {"pearson_r_temp": round(r_all, 3), "pearson_r_abs_dev_from_18c": round(r_dev, 3),
           "weekday_mean_by_band": _bands(weekday),
           "semester_weekday_mean_by_band": _bands(semester),
           "vacation_weekday_mean_by_band": _bands(vacation),
           "n_weekdays": int(len(weekday)),
           "note": "전체 평일 구간 평균은 '여름=방학' 효과와 섞인다. 학기/방학을 나눈 값으로 냉난방 효과를 본다"}
    if len(semester) >= 30:
        out["semester_pearson_r_abs_dev_from_18c"] = round(float(semester["value"].corr((semester["temp_c"] - 18).abs())), 3)
    if len(vacation) >= 30:
        out["vacation_pearson_r_abs_dev_from_18c"] = round(float(vacation["value"].corr((vacation["temp_c"] - 18).abs())), 3)
    return out


def recent_trend(df: pd.DataFrame, window: int = 7, band: float = TREND_BAND) -> dict:
    """최근 window일 평균 vs 직전 window일 평균. M-2 summary.trend와 같은 규칙."""
    values = df["value"].dropna()
    if len(values) < window * 2:
        return {"trend": "not_enough_data", "recent_avg": None, "previous_avg": None, "change_pct": None}
    recent = float(values.iloc[-window:].mean())
    previous = float(values.iloc[-2 * window:-window].mean())
    change = (recent / previous - 1) if previous else 0.0
    trend = "increasing" if change > band else "decreasing" if change < -band else "stable"
    return {"trend": trend, "recent_avg": round(recent, 1), "previous_avg": round(previous, 1),
            "change_pct": round(change * 100, 1), "window_days": window}


def run_all(df: pd.DataFrame) -> pd.DataFrame:
    """정제된 df에 모든 파생 컬럼을 붙인다."""
    df = add_calendar(df)
    df = add_moving_averages(df)
    df = add_change_rates(df)
    df = add_volatility(df)
    df = flag_outliers(df)
    return df
