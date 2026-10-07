"""전력거래소 '시간별 전국 전력수요량' CSV(날짜 + 1시~24시 열, MWh) → 일별 합계 CSV(date,value,is_holiday,memo)

사용: python src/convert_kpx.py "data/real/한국전력거래소_시간별 전국 전력수요량_20251231.csv" data/real/kpx_daily_2025.csv
- 24개 시간 열을 더해 일별 MWh를 만든다 (단위는 그대로 MWh)
- 공휴일 표시는 make_sample.py의 HOLIDAYS 목록을 재사용한다
- 원본 파일은 수정하지 않는다
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from load import read_csv_any  # noqa: E402
from make_sample import HOLIDAYS  # noqa: E402


def convert(src: Path, dst: Path) -> pd.DataFrame:
    raw = read_csv_any(src)
    date_col = raw.columns[0]
    hour_cols = [c for c in raw.columns if str(c).strip().rstrip("시").isdigit()]
    if len(hour_cols) != 24:
        raise ValueError(f"시간 열이 24개가 아닙니다: {len(hour_cols)}개 → {hour_cols[:5]}…")
    df = pd.DataFrame({
        "date": pd.to_datetime(raw[date_col].astype(str).str.strip(), errors="coerce"),
        "value": raw[hour_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1).round(1),
    }).dropna(subset=["date"]).sort_values("date")
    key = df["date"].dt.strftime("%Y-%m-%d")
    df["is_holiday"] = key.isin(HOLIDAYS.keys()).astype(int)
    df["memo"] = key.map(HOLIDAYS).fillna("")
    df["date"] = key
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dst, index=False, encoding="utf-8")
    return df


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    out = convert(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{sys.argv[2]}: {len(out)}행, {out['date'].iloc[0]} ~ {out['date'].iloc[-1]}, "
          f"일평균 {out['value'].mean():,.0f} MWh, 공휴일 {int(out['is_holiday'].sum())}일")
