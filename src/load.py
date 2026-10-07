"""데이터 로딩·정제.

- CSV 인코딩 자동 판별(utf-8-sig → utf-8 → cp949)
- 날짜·값 컬럼을 이름으로 지정하거나 키워드로 자동 탐색
- 기본 정보(기간·행 수·결측치) 요약
- 결측치 기준: 연속 3일 이하는 선형 보간, 그보다 길면 결측 유지(리포트 4장 "전처리 기준")
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATE_KEYWORDS = ("date", "일자", "날짜", "일시", "기준일", "ymd", "dt")
VALUE_KEYWORDS = ("value", "kwh", "사용량", "전력", "소비", "판매량", "수요", "발전량", "amount")
TEMP_KEYWORDS = ("temp", "기온", "온도")
MAX_INTERPOLATE_GAP = 3


def read_csv_any(path: str | Path) -> pd.DataFrame:
    """인코딩을 차례로 시도해 CSV를 읽는다."""
    last_error: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_error = e
    raise ValueError(f"CSV 인코딩을 판별하지 못했습니다: {path} ({last_error})")


def _find_column(columns, keywords, explicit: str | None) -> str | None:
    if explicit:
        if explicit not in columns:
            raise KeyError(f"컬럼 '{explicit}'이 없습니다. 있는 컬럼: {list(columns)}")
        return explicit
    lowered = {c: str(c).lower() for c in columns}
    for c, low in lowered.items():
        if any(k in low for k in keywords):
            return c
    return None


def load_series(path: str | Path, date_col: str | None = None, value_col: str | None = None,
                temp_col: str | None = None) -> pd.DataFrame:
    """CSV → 표준 컬럼(date, value[, temp_c, memo, is_holiday])의 일별 DataFrame.

    날짜는 오름차순 정렬, 중복 날짜는 평균으로 합친다. 빠진 날짜는 행을 만들어 NaN으로 둔다(보간은 clean()에서).
    """
    raw = read_csv_any(path)
    d_col = _find_column(raw.columns, DATE_KEYWORDS, date_col)
    v_col = _find_column(raw.columns, VALUE_KEYWORDS, value_col)
    if d_col is None or v_col is None:
        raise KeyError(f"날짜/값 컬럼을 찾지 못했습니다. --date-col/--value-col 로 지정하세요. 컬럼: {list(raw.columns)}")
    t_col = _find_column(raw.columns, TEMP_KEYWORDS, temp_col)

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[d_col], errors="coerce"),
        "value": pd.to_numeric(raw[v_col].astype(str).str.replace(",", ""), errors="coerce"),
    })
    if t_col is not None:
        df["temp_c"] = pd.to_numeric(raw[t_col], errors="coerce")
    for extra in ("memo", "is_holiday"):
        if extra in raw.columns:
            df[extra] = raw[extra]

    df = df.dropna(subset=["date"]).sort_values("date")
    # 중복 날짜는 수치 평균, 문자열은 첫 값
    agg = {"value": "mean"}
    if "temp_c" in df:
        agg["temp_c"] = "mean"
    if "memo" in df:
        agg["memo"] = "first"
    if "is_holiday" in df:
        agg["is_holiday"] = "max"
    df = df.groupby("date", as_index=False).agg(agg)

    # 빠진 날짜 채우기(값은 NaN)
    full_index = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    df = df.set_index("date").reindex(full_index).rename_axis("date").reset_index()
    if "memo" in df:
        df["memo"] = df["memo"].fillna("")
    if "is_holiday" in df:
        df["is_holiday"] = df["is_holiday"].fillna(0).astype(int)
    return df


def describe(df: pd.DataFrame) -> dict:
    """기본 정보: 기간·행 수·결측치·요약 통계."""
    value = df["value"]
    info = {
        "start": df["date"].min().strftime("%Y-%m-%d"),
        "end": df["date"].max().strftime("%Y-%m-%d"),
        "rows": int(len(df)),
        "missing_value": int(value.isna().sum()),
        "columns": list(df.columns),
        "mean": round(float(value.mean()), 1),
        "std": round(float(value.std()), 1),
        "min": round(float(value.min()), 1),
        "max": round(float(value.max()), 1),
    }
    if "temp_c" in df:
        info["missing_temp"] = int(df["temp_c"].isna().sum())
    return info


def clean(df: pd.DataFrame, max_gap: int = MAX_INTERPOLATE_GAP) -> tuple[pd.DataFrame, dict]:
    """결측치 처리. 연속 max_gap일 이하만 선형 보간, 그 이상은 그대로 둔다. 처리 내역을 함께 돌려준다."""
    df = df.copy()
    before = int(df["value"].isna().sum())
    is_na = df["value"].isna()
    # 연속 결측 구간 길이 계산
    group = (is_na != is_na.shift()).cumsum()
    run_len = is_na.groupby(group).transform("sum")
    short_gap = is_na & (run_len <= max_gap)
    interpolated = df["value"].interpolate(method="linear", limit_area="inside")
    df.loc[short_gap, "value"] = interpolated[short_gap]
    df["interpolated"] = short_gap
    after = int(df["value"].isna().sum())
    log = {
        "missing_before": before,
        "interpolated": int(short_gap.sum()),
        "missing_after": after,
        "rule": f"연속 {max_gap}일 이하 결측은 선형 보간, 초과 구간은 결측 유지",
    }
    return df, log
