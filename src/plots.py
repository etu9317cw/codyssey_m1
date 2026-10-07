"""시각화 5장 저장 (images/01~05). 한글 폰트는 Windows 기본 '맑은 고딕'."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analyze import WEEKDAY_KO  # noqa: E402

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
DPI = 150
UNIT = "kWh"


def _save(fig, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return str(path)


def plot_trend_ma(df: pd.DataFrame, out_dir: Path, title_suffix: str = "") -> str:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df["date"], df["value"], color="#9bb5c9", lw=0.8, label="일별 사용량")
    ax.plot(df["date"], df["ma7"], color="#1f6f8b", lw=1.6, label="7일 이동평균")
    ax.plot(df["date"], df["ma30"], color="#d35400", lw=2.0, label="30일 이동평균")
    ax.set_title(f"일별 전력 사용량과 이동평균{title_suffix}")
    ax.set_ylabel(UNIT)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    return _save(fig, out_dir / "01_trend_moving_average.png")


def plot_monthly(monthly: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    months = monthly.index.tolist()
    colors = ["#1f6f8b" if int(m[-2:]) in (3, 4, 5, 6, 9, 10, 11, 12) else "#e0a458" for m in months]
    ax.bar(months, monthly["mean"], color=colors)
    ax.set_title("월별 일평균 전력 사용량 (파랑: 학기, 주황: 방학)")
    ax.set_ylabel(f"일평균 {UNIT}")
    ax.tick_params(axis="x", rotation=60, labelsize=8)
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, out_dir / "02_monthly_mean.png")


def plot_weekday(weekday: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#1f6f8b"] * 5 + ["#c0392b", "#c0392b"]
    bars = ax.bar(weekday["weekday_ko"], weekday["mean"], yerr=weekday["std"], capsize=4, color=colors, alpha=0.9)
    for b, pct in zip(bars, weekday["vs_weekday_pct"]):
        ax.annotate(f"{pct:+.0f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=9, xytext=(0, 4), textcoords="offset points")
    ax.set_title("요일별 평균 전력 사용량 (오차 막대: 표준편차, 숫자: 평일 평균 대비)")
    ax.set_ylabel(UNIT)
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, out_dir / "03_weekday_mean.png")


def plot_outliers(df: pd.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df["date"], df["value"], color="#9bb5c9", lw=0.8, label="일별 사용량")
    ax.plot(df["date"], df["weekday_mean"], color="#7f8c8d", lw=0.8, ls="--", label="기준값(학기/방학·날 유형·요일별 평균)")
    up = df[df["outlier"] & (df["dev_from_weekday_mean"] > 0)]
    down = df[df["outlier"] & (df["dev_from_weekday_mean"] < 0)]
    ax.scatter(up["date"], up["value"], color="#c0392b", s=28, zorder=3, label=f"급증 이상치 {len(up)}일")
    ax.scatter(down["date"], down["value"], color="#2980b9", s=28, zorder=3, label=f"급감 이상치 {len(down)}일")
    ax2 = ax.twinx()
    ax2.plot(df["date"], df["std30"], color="#8e44ad", lw=1.0, alpha=0.6, label="30일 이동 표준편차")
    ax2.set_ylabel("표준편차 (kWh)", color="#8e44ad")
    ax.set_title("이상치(기준값 대비 ±30%)와 30일 변동성")
    ax.set_ylabel(UNIT)
    ax.grid(alpha=0.3)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    return _save(fig, out_dir / "04_outliers_volatility.png")


def plot_forecast(actual: pd.Series, predicted: pd.Series, dates: pd.Series, mae: float, mape: float, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(dates, actual, color="#1f6f8b", lw=1.5, marker="o", ms=3, label="실제")
    ax.plot(dates, predicted, color="#d35400", lw=1.5, ls="--", marker="x", ms=4, label="베이스라인 예측 (최근 4주 같은 요일 평균)")
    ax.set_title(f"보너스 2 — 베이스라인 예측 vs 실제 (홀드아웃 {len(actual)}일, MAE {mae:,.0f} kWh, MAPE {mape:.1f}%)")
    ax.set_ylabel(UNIT)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    return _save(fig, out_dir / "05_baseline_forecast.png")
