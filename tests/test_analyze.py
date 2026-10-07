"""분석 모듈 단위 테스트 — 작은 합성 데이터로 규칙이 맞게 동작하는지 확인."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import analyze  # noqa: E402
import forecast  # noqa: E402
import load  # noqa: E402


def make_df(days=70, start="2026-01-05", weekday_value=1000.0, weekend_value=500.0):
    dates = pd.date_range(start, periods=days, freq="D")
    values = [weekend_value if d.weekday() >= 5 else weekday_value for d in dates]
    return pd.DataFrame({"date": dates, "value": values, "is_holiday": 0, "memo": ""})


def test_moving_average_constant_series():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=40), "value": 100.0})
    out = analyze.add_moving_averages(df)
    assert out["ma7"].iloc[-1] == pytest.approx(100.0)
    assert out["ma30"].iloc[-1] == pytest.approx(100.0)


def test_change_rate_doubling():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "value": [100.0, 200.0, 100.0]})
    out = analyze.add_change_rates(df)
    assert out["pct_change_1d"].iloc[1] == pytest.approx(100.0)
    assert out["pct_change_1d"].iloc[2] == pytest.approx(-50.0)


def test_weekday_summary_weekend_ratio():
    df = analyze.add_calendar(make_df())
    wk = analyze.weekday_summary(df)
    assert wk.loc[5, "mean"] == pytest.approx(500.0)
    assert wk.loc[5, "vs_weekday_pct"] == pytest.approx(-50.0)
    assert wk.loc[0, "vs_weekday_pct"] == pytest.approx(0.0)


def test_outlier_flag_only_marks_not_removes():
    df = analyze.add_calendar(make_df())
    df.loc[10, "value"] = 1000.0 * 0.5   # 평일 값을 절반으로 → 같은 요일 평균 대비 -40%대 → 이상치
    n_before = len(df)
    out = analyze.flag_outliers(df)
    assert len(out) == n_before
    assert bool(out.loc[10, "outlier"]) is True
    assert out.loc[10, "outlier_direction"] == "급감"
    assert out["outlier"].sum() == 1


def test_calendar_period_and_day_type():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-03-02", "2026-07-15", "2026-03-07"]),
                       "value": [1.0, 1.0, 1.0], "is_holiday": [0, 0, 0]})
    out = analyze.add_calendar(df)
    assert list(out["period"]) == ["학기", "방학", "학기"]
    assert list(out["day_type"]) == ["평일", "평일", "주말"]


def test_recent_trend_rules():
    up = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=14), "value": [100.0] * 7 + [120.0] * 7})
    assert analyze.recent_trend(up)["trend"] == "increasing"
    down = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=14), "value": [100.0] * 7 + [80.0] * 7})
    assert analyze.recent_trend(down)["trend"] == "decreasing"
    flat = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=14), "value": [100.0] * 7 + [102.0] * 7})
    assert analyze.recent_trend(flat)["trend"] == "stable"
    short = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=5), "value": 1.0})
    assert analyze.recent_trend(short)["trend"] == "not_enough_data"


def test_clean_interpolates_short_gaps_only():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=12), "value": 100.0})
    df.loc[2:3, "value"] = np.nan        # 2일 결측 → 보간
    df.loc[6:10, "value"] = np.nan       # 5일 결측 → 유지
    out, log = load.clean(df, max_gap=3)
    assert log["missing_before"] == 7
    assert log["interpolated"] == 2
    assert log["missing_after"] == 5
    assert out.loc[2, "value"] == pytest.approx(100.0)


def test_baseline_forecast_perfect_on_weekly_pattern():
    df = make_df(days=70)
    result = forecast.evaluate(df, holdout_days=14, weeks=4)
    assert result["metrics"]["mae"] == pytest.approx(0.0)
    assert result["metrics"]["holdout_days"] == 14


def test_load_series_auto_columns(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("일자,사용량(kWh)\n2026-01-01,\"1,000\"\n2026-01-03,1200\n", encoding="cp949")
    df = load.load_series(csv)
    assert list(df.columns)[:2] == ["date", "value"]
    assert len(df) == 3                      # 빠진 1/2가 NaN 행으로 생김
    assert df["value"].iloc[0] == 1000.0
    assert pd.isna(df["value"].iloc[1])
