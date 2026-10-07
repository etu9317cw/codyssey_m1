"""전체 파이프라인 실행: 로딩 → 정제 → 분석 → 시각화 5장 → output/summary.json, summary.txt

사용:
  python src/run.py --source sample
  python src/run.py --source real --file data/real/xxx.csv [--date-col 일자 --value-col 사용량]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze  # noqa: E402
import forecast  # noqa: E402
import load  # noqa: E402
import plots  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = {"sample": ROOT / "data" / "sample" / "electricity_daily.csv"}


def build_summary(df: pd.DataFrame, info: dict, clean_log: dict, monthly: pd.DataFrame, weekday: pd.DataFrame,
                  period: pd.DataFrame, corr: dict | None, trend: dict, fc: dict | None, source: str, file: Path) -> dict:
    values = df["value"].dropna()
    last7 = values.iloc[-7:]
    outliers = df[df["outlier"]]
    sem = df[df["period"] == "학기"]["value"].mean()
    vac = df[df["period"] == "방학"]["value"].mean()
    weekday_mean = df[df["day_type"] == "평일"]["value"].mean()
    weekend_mean = df[df["day_type"] == "주말"]["value"].mean()
    holiday_mean = df[df["day_type"] == "공휴일"]["value"].mean()

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "file": str(file.relative_to(ROOT)) if file.is_relative_to(ROOT) else str(file),
        "is_simulated": source == "sample",
        "unit": plots.UNIT,
        "period": {"start": info["start"], "end": info["end"]},
        "count": int(values.count()),
        "metrics": {"total": round(float(values.sum()), 1), "average": round(float(values.mean()), 1),
                    "max": round(float(values.max()), 1), "min": round(float(values.min()), 1),
                    "std": round(float(values.std()), 1)},
        "recent_7_days": {"total": round(float(last7.sum()), 1), "average": round(float(last7.mean()), 1)},
        "trend": trend["trend"],
        "trend_detail": trend,
        "preprocessing": clean_log,
        "semester_vs_vacation": {"semester_mean": round(float(sem), 1), "vacation_mean": round(float(vac), 1),
                                 "ratio_pct": round(float(sem / vac * 100 - 100), 1)},
        "day_type": {"weekday_mean": round(float(weekday_mean), 1), "weekend_mean": round(float(weekend_mean), 1),
                     "holiday_mean": round(float(holiday_mean), 1) if pd.notna(holiday_mean) else None,
                     "weekend_vs_weekday_pct": round(float(weekend_mean / weekday_mean * 100), 1),
                     "holiday_vs_weekday_pct": round(float(holiday_mean / weekday_mean * 100), 1) if pd.notna(holiday_mean) else None},
        "monthly": monthly.reset_index().to_dict(orient="records"),
        "weekday": weekday.reset_index().to_dict(orient="records"),
        "period_day_type": [{"period": p, "day_type": d, **row} for (p, d), row in period.to_dict(orient="index").items()],
        "outliers": {"count": int(len(outliers)), "rule": "학기/방학·날 유형·요일별 기준값 대비 ±30%",
                     "days": [{"date": r.date.strftime("%Y-%m-%d"), "value": round(float(r.value), 1),
                               "deviation_pct": round(float(r.dev_from_weekday_mean), 1), "direction": r.outlier_direction,
                               "memo": str(getattr(r, "memo", ""))} for r in outliers.itertuples()]},
        "volatility": {"std30_mean": round(float(df["std30"].mean()), 1),
                       "std30_max": round(float(df["std30"].max()), 1),
                       "std30_max_date": df.loc[df["std30"].idxmax(), "date"].strftime("%Y-%m-%d") if df["std30"].notna().any() else None},
        "max_change": {"date": df.loc[df["pct_change_1d"].abs().idxmax(), "date"].strftime("%Y-%m-%d"),
                       "pct_change_1d": round(float(df["pct_change_1d"].abs().max()), 1)},
        "temperature": corr,
        "top_memo": (df["memo"].replace("", pd.NA).dropna().str.split().str[0].value_counts().index[0]
                     if "memo" in df and df["memo"].replace("", pd.NA).notna().any() else None),
        "forecast": fc,
    }
    return summary


def write_summary_txt(s: dict, path: Path) -> None:
    """리포트에 그대로 붙여 넣을 수치 문장."""
    m, d, sv = s["metrics"], s["day_type"], s["semester_vs_vacation"]
    lines = [
        f"[데이터] {s['period']['start']} ~ {s['period']['end']}, {s['count']}일, 단위 {s['unit']}, 출처 {s['file']}" + (" (시뮬레이션)" if s["is_simulated"] else ""),
        f"[전처리] 결측 {s['preprocessing']['missing_before']}건 → 보간 {s['preprocessing']['interpolated']}건, 남은 결측 {s['preprocessing']['missing_after']}건 ({s['preprocessing']['rule']})",
        f"[기초] 평균 {m['average']:,} / 최소 {m['min']:,} / 최대 {m['max']:,} / 표준편차 {m['std']:,}",
        f"[Q1 학기 vs 방학] 학기 일평균 {sv['semester_mean']:,} vs 방학 {sv['vacation_mean']:,} → 학기가 {sv['ratio_pct']:+.1f}%",
        f"[Q2 요일] 평일 {d['weekday_mean']:,} / 주말 {d['weekend_mean']:,} ({d['weekend_vs_weekday_pct']}%) / 공휴일 {d['holiday_mean']} ({d['holiday_vs_weekday_pct']}%)",
        f"[Q2 이상치] {s['outliers']['count']}일 ({s['outliers']['rule']}): " + ", ".join(f"{o['date']} {o['direction']} {o['deviation_pct']:+.0f}%" for o in s["outliers"]["days"]),
        f"[Q3 추세] 최근 7일 평균 {s['trend_detail'].get('recent_avg')} vs 직전 7일 {s['trend_detail'].get('previous_avg')} → {s['trend']} ({s['trend_detail'].get('change_pct')}%)",
        f"[변동성] 30일 이동 표준편차 평균 {s['volatility']['std30_mean']:,}, 최대 {s['volatility']['std30_max']:,} ({s['volatility']['std30_max_date']})",
        f"[최대 일변화] {s['max_change']['date']} 전일 대비 {s['max_change']['pct_change_1d']}%",
    ]
    if s["temperature"]:
        t = s["temperature"]
        lines.append(f"[Q3 기온] 평일 {t['n_weekdays']}일, 기온 r={t['pearson_r_temp']}, |기온-18℃| r={t['pearson_r_abs_dev_from_18c']} (학기만 r={t.get('semester_pearson_r_abs_dev_from_18c')}, 방학만 r={t.get('vacation_pearson_r_abs_dev_from_18c')})")
        lines.append(f"[Q3 기온 구간 평균] 전체 평일 {t['weekday_mean_by_band']} / 학기 평일 {t['semester_weekday_mean_by_band']} / 방학 평일 {t['vacation_weekday_mean_by_band']}")
    if s["forecast"]:
        f = s["forecast"]
        lines.append(f"[보너스2 예측] {f['method']}: MAE {f['mae']:,} / MAPE {f['mape_pct']}% (naive-7: MAE {f['naive7_mae']:,} / MAPE {f['naive7_mape_pct']}%), 홀드아웃 {f['holdout_days']}일")
    lines.append("[월별 일평균] " + ", ".join(f"{r['month']} {r['mean']:,.0f}" for r in s["monthly"]))
    lines.append("[요일별 평균] " + ", ".join(f"{r['weekday_ko']} {r['mean']:,.0f}({r['vs_weekday_pct']:+.0f}%)" for r in s["weekday"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["sample", "real"], default="sample")
    parser.add_argument("--file", help="CSV 경로 (real일 때 필수, sample은 기본 경로)")
    parser.add_argument("--date-col")
    parser.add_argument("--value-col")
    parser.add_argument("--temp-col")
    parser.add_argument("--holdout", type=int, default=60)
    parser.add_argument("--no-forecast", action="store_true")
    parser.add_argument("--tag", help="출력 하위 폴더 이름 (예: real → images/real, output/real). 없으면 루트에 저장")
    parser.add_argument("--unit", default="kWh", help="값 단위 표기 (sample=kWh, KPX 실데이터=MWh)")
    args = parser.parse_args()

    file = Path(args.file) if args.file else DEFAULT_FILES.get(args.source)
    if file is None or not file.exists():
        print(f"데이터 파일이 없습니다: {file}. real이면 --file 로 지정하세요.")
        return 2

    images = ROOT / "images" / args.tag if args.tag else ROOT / "images"
    output = ROOT / "output" / args.tag if args.tag else ROOT / "output"
    output.mkdir(parents=True, exist_ok=True)
    plots.UNIT = args.unit

    print(f"① 로딩 {file}")
    df = load.load_series(file, args.date_col, args.value_col, args.temp_col)
    info = load.describe(df)
    print(f"   {info['start']} ~ {info['end']}, {info['rows']}행, 결측 {info['missing_value']}")

    print("② 정제")
    df, clean_log = load.clean(df)
    print(f"   {clean_log}")

    print("③ 분석")
    df = analyze.run_all(df)
    monthly = analyze.monthly_summary(df)
    weekday = analyze.weekday_summary(df)
    period = analyze.period_summary(df)
    corr = analyze.temperature_correlation(df)
    trend = analyze.recent_trend(df)

    fc = None
    if not args.no_forecast and len(df) >= args.holdout + 35:
        print("④ 베이스라인 예측")
        result = forecast.evaluate(df, holdout_days=args.holdout)
        fc = result["metrics"]

    print("⑤ 시각화")
    suffix = " (시뮬레이션 데이터)" if args.source == "sample" else " (실데이터)"
    saved = [plots.plot_trend_ma(df, images, suffix), plots.plot_monthly(monthly, images),
             plots.plot_weekday(weekday, images), plots.plot_outliers(df, images)]
    if fc:
        fr = result["frame"]
        saved.append(plots.plot_forecast(fr["actual"], fr["predicted"], fr["date"], fc["mae"], fc["mape_pct"], images))
    for p in saved:
        print(f"   {Path(p).relative_to(ROOT)}")

    print("⑥ 요약 저장")
    summary = build_summary(df, info, clean_log, monthly, weekday, period, corr, trend, fc, args.source, file)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_summary_txt(summary, output / "summary.txt")
    df.to_csv(output / "analyzed.csv", index=False, encoding="utf-8-sig")
    print(f"   output/summary.json, output/summary.txt, output/analyzed.csv")
    print()
    print((output / "summary.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
