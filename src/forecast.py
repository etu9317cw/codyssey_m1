"""보너스 2-B: 베이스라인 예측.

예측 규칙: 예측일과 같은 요일의 **직전 4주 평균**(해당 날짜 이전 데이터만 사용 → 미래 정보 누출 없음).
홀드아웃: 마지막 N일(기본 60일). 정확도보다 "가정과 한계"를 설명하는 것이 목적이다.
비교용 더 단순한 기준: 전주 같은 요일 값(naive-7).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def baseline_same_weekday(values: pd.Series, weeks: int = 4) -> pd.Series:
    """각 시점의 예측값 = 7, 14, 21, 28일 전 값들의 평균 (존재하는 것만)."""
    lags = [values.shift(7 * k) for k in range(1, weeks + 1)]
    return pd.concat(lags, axis=1).mean(axis=1, skipna=True)


def evaluate(df: pd.DataFrame, holdout_days: int = 60, weeks: int = 4) -> dict:
    """마지막 holdout_days 구간에서 MAE·MAPE 계산. 반환에 그래프용 시리즈 포함."""
    series = df.set_index("date")["value"]
    pred_all = baseline_same_weekday(series, weeks=weeks)
    naive_all = series.shift(7)

    test_idx = series.index[-holdout_days:]
    actual = series.loc[test_idx]
    pred = pred_all.loc[test_idx]
    naive = naive_all.loc[test_idx]
    mask = actual.notna() & pred.notna()

    def _mae(a, p):
        return float(np.mean(np.abs(a - p)))

    def _mape(a, p):
        a, p = a[a != 0], p[a != 0]
        return float(np.mean(np.abs((a - p) / a)) * 100)

    result = {
        "method": f"같은 요일 직전 {weeks}주 평균",
        "holdout_days": int(mask.sum()),
        "mae": round(_mae(actual[mask], pred[mask]), 1),
        "mape_pct": round(_mape(actual[mask], pred[mask]), 1),
        "naive7_mae": round(_mae(actual[mask], naive[mask]), 1),
        "naive7_mape_pct": round(_mape(actual[mask], naive[mask]), 1),
        "assumptions": [
            "요일 패턴이 4주 안에서는 유지된다",
            "학기·방학 전환, 공휴일, 정전 같은 사건은 예측에 반영되지 않는다",
            "추세(연 +3%)는 4주 평균에 자연히 일부 반영되지만 명시적으로 모델링하지 않았다",
        ],
        "limits": [
            "공휴일·이상치 날의 오차가 크다 (같은 요일 평균이 그 날을 설명하지 못함)",
            "학기 시작·종료 직후 1~2주는 과거 4주가 다른 구간이라 체계적으로 틀린다",
            "단일 수치 예측이며 구간(불확실성)을 제시하지 않는다",
        ],
    }
    frame = pd.DataFrame({"date": test_idx, "actual": actual.values, "predicted": pred.values, "naive7": naive.values})
    return {"metrics": result, "frame": frame}
