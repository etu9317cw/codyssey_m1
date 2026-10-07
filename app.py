"""보너스 1 — Streamlit 대시보드: 기간·요일·구간 필터로 전력 사용량을 탐색한다.

실행:  streamlit run app.py
데이터: data/sample/electricity_daily.csv (기본) 또는 사이드바에서 CSV 업로드
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import analyze  # noqa: E402
import load  # noqa: E402

st.set_page_config(page_title="센터 교육동 전력 사용량 대시보드", layout="wide")
DEFAULT = ROOT / "data" / "sample" / "electricity_daily.csv"


@st.cache_data(show_spinner=False)
def prepare(path_or_buffer) -> pd.DataFrame:
    df = load.load_series(path_or_buffer)
    df, _ = load.clean(df)
    return analyze.run_all(df)


# ---------- 사이드바 ----------
st.sidebar.header("데이터·필터")
uploaded = st.sidebar.file_uploader("CSV 업로드 (date, value 컬럼)", type="csv")
source_label = "업로드 파일" if uploaded else "시뮬레이션 데이터 (data/sample)"
df_all = prepare(uploaded if uploaded else DEFAULT)
st.sidebar.caption(f"출처: {source_label} · {len(df_all)}일")

min_d, max_d = df_all["date"].min().date(), df_all["date"].max().date()
start, end = st.sidebar.date_input("기간", (min_d, max_d), min_value=min_d, max_value=max_d)
periods = st.sidebar.multiselect("구간", ["학기", "방학"], default=["학기", "방학"])
day_types = st.sidebar.multiselect("날 유형", ["평일", "주말", "공휴일"], default=["평일", "주말", "공휴일"])
ma_window = st.sidebar.select_slider("이동평균 창(일)", options=[7, 14, 30, 60], value=30)
show_outliers = st.sidebar.checkbox("이상치 표시", value=True)

mask = (df_all["date"].dt.date >= start) & (df_all["date"].dt.date <= end)
mask &= df_all["period"].isin(periods) & df_all["day_type"].isin(day_types)
df = df_all[mask].copy()
df[f"ma{ma_window}"] = df["value"].rolling(ma_window, min_periods=max(1, ma_window // 2)).mean()

# ---------- 헤더·요약 카드 ----------
st.title("센터 교육동 전력 사용량 대시보드")
st.caption("3단계 M-1 보너스 1 · 필터를 바꾸면 모든 카드·그래프가 다시 계산됩니다 · 시뮬레이션 데이터 기준")

if df.empty:
    st.warning("선택한 조건에 데이터가 없습니다. 필터를 넓혀 주세요.")
    st.stop()

trend = analyze.recent_trend(df)
trend_ko = {"increasing": "증가", "decreasing": "감소", "stable": "유지", "not_enough_data": "데이터 부족"}[trend["trend"]]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("기간", f"{df['date'].min():%Y-%m-%d} ~ {df['date'].max():%m-%d}", f"{len(df)}일")
c2.metric("일평균 (kWh)", f"{df['value'].mean():,.0f}", f"표준편차 {df['value'].std():,.0f}")
c3.metric("최대 / 최소", f"{df['value'].max():,.0f} / {df['value'].min():,.0f}")
c4.metric("최근 7일 추세", trend_ko, f"{trend['change_pct']:+.1f}%" if trend["change_pct"] is not None else None)
c5.metric("이상치", f"{int(df['outlier'].sum())}일", "기준값 대비 ±30%")

# ---------- 탭 ----------
tab1, tab2, tab3 = st.tabs(["추세", "집계", "이상치·변동성"])

with tab1:
    st.subheader(f"일별 사용량과 {ma_window}일 이동평균")
    chart = df.set_index("date")[["value", f"ma{ma_window}"]].rename(columns={"value": "일별", f"ma{ma_window}": f"{ma_window}일 이동평균"})
    st.line_chart(chart, height=360)
    st.subheader("전주 대비 변화율 (%)")
    st.bar_chart(df.set_index("date")["pct_change_7d"], height=220)

with tab2:
    left, right = st.columns(2)
    with left:
        st.subheader("월별 일평균")
        monthly = analyze.monthly_summary(df)
        st.bar_chart(monthly["mean"], height=320)
        st.dataframe(monthly, use_container_width=True, height=240)
    with right:
        st.subheader("요일별 평균")
        weekday = analyze.weekday_summary(df).set_index("weekday_ko")
        st.bar_chart(weekday["mean"], height=320)
        st.dataframe(weekday[["mean", "std", "days", "vs_weekday_pct"]], use_container_width=True, height=240)
    st.subheader("구간 × 날 유형 평균")
    st.dataframe(analyze.period_summary(df), use_container_width=True)

with tab3:
    st.subheader("30일 이동 표준편차 (변동성)")
    st.line_chart(df.set_index("date")["std30"], height=260)
    if show_outliers:
        st.subheader("이상치 목록 (학기/방학·날 유형·요일별 기준값 대비 ±30%, 제거하지 않고 표시)")
        cols = ["date", "value", "weekday_mean", "dev_from_weekday_mean", "outlier_direction"]
        if "memo" in df:
            cols.append("memo")
        out = df[df["outlier"]][cols].rename(columns={
            "date": "날짜", "value": "사용량", "weekday_mean": "기준값", "dev_from_weekday_mean": "편차(%)", "outlier_direction": "방향", "memo": "메모"})
        st.dataframe(out.round(1), use_container_width=True)

with st.expander("이 대시보드가 쓰는 규칙"):
    st.markdown(
        "- **구간**: 3~6월·9~12월 = 학기, 1~2월·7~8월 = 방학\n"
        "- **날 유형**: 공휴일(데이터의 is_holiday) > 주말(토·일) > 평일\n"
        "- **추세**: 최근 7일 평균 vs 직전 7일 평균, ±5% 안이면 유지\n"
        "- **이상치**: (구간, 날 유형, 요일) 평균을 기준값으로 ±30% 벗어난 날. 값은 바꾸지 않는다\n"
        "- 분석 코드는 `src/analyze.py`와 동일 (리포트와 같은 숫자가 나온다)")
