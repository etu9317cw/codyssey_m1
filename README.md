# 센터 교육동 일별 전력 사용량 시계열 분석 (M-1)

대학교 에너지인력양성센터가 관리하는 교육동의 **일별 전력 사용량(kWh)** 2년치를 분석한 3단계 M-1 과제입니다.
학기/방학·요일·공휴일·기온이 사용량에 미치는 영향을 이동평균·변화율·집계·변동성 네 기법으로 보고, 이상치를 규칙으로 찾고, 베이스라인 예측과 Streamlit 대시보드(보너스)까지 만들었습니다.

| 항목 | 위치 |
|---|---|
| **분석 리포트** | [`REPORT.md`](./REPORT.md) — 질문 3개, 전처리 기준, 시각화 5장, 인사이트 4개, 결론·한계, AI 사용 로그, **미션 요구사항 대조표(11장)** |
| 시각화 | `images/01~05_*.png`, 대시보드 캡처 `images/dash_01~03_*.png`, 실데이터 결과 `images/real/` — 리포트에 10장 삽입 |
| 코드 | `src/` (load → analyze → plots → forecast → run), `make_sample.py`, `app.py` |
| 데이터 | `data/sample/` 시뮬레이션 730일, `data/real/` 전력거래소 실데이터 365일 — 설명은 [`data/README.md`](./data/README.md) |
| 결과 수치 | `output/summary.json`(M-2 비서가 읽는 형식), `output/summary.txt`(리포트 인용용) |
| 테스트 | `tests/test_analyze.py` (pytest 9개) |
| GitHub | `https://github.com/etu9317cw/codyssey_m1` |

> 기본 데이터는 **시뮬레이션**입니다(센터 건물 계량값은 외부에서 받을 수 없음). 생성 규칙과 시드를 공개했고, 같은 코드가 실데이터(전국 전력수요)에서도 동작함을 리포트 7-3에서 확인했습니다.

## 설치·실행

Python 3.10 이상 (개발: 3.14.7, Windows 11).

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # PowerShell 실행 정책 오류 시: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt       # 정확한 버전은 requirements-lock.txt

python make_sample.py                 # (선택) 샘플 데이터 재생성 — 같은 seed면 같은 파일
python src/run.py --source sample     # 전체 분석: images/, output/summary.json·txt
python -m pytest tests -q             # 9 passed
streamlit run app.py                  # 보너스 1 대시보드 (http://localhost:8501)
```

Windows 터미널에서 한글이 깨지면 `python -X utf8 ...`로 실행합니다.

### 실데이터로 실행

```
python src/convert_kpx.py "data/real/한국전력거래소_시간별 전국 전력수요량_20251231.csv" data/real/kpx_daily_2025.csv
python src/run.py --source real --file data/real/kpx_daily_2025.csv --tag real --unit MWh
```

다른 CSV도 `--file`로 넣을 수 있습니다. 날짜·값 컬럼은 이름 키워드로 자동 탐색하고, 안 되면 `--date-col`·`--value-col`로 지정합니다. 인코딩(utf-8/cp949)은 자동 판별합니다.

## 폴더 구조

```
.
├── README.md                 # 이 문서
├── REPORT.md                 # 분석 리포트 (제출물 1)
├── make_sample.py            # 시뮬레이션 데이터 생성기 (규칙·seed 고정)
├── app.py                    # 보너스 1 Streamlit 대시보드
├── requirements.txt / requirements-lock.txt
├── data/
│   ├── README.md             # 컬럼·생성 규칙·실데이터 교체 방법·라이선스
│   ├── sample/electricity_daily.csv
│   └── real/                 # 전력거래소 원본 CSV, 변환본, source.md(출처·라이선스)
├── src/
│   ├── load.py               # 로딩·인코딩·컬럼 탐색·결측 보간(연속 3일 이하)
│   ├── analyze.py            # 이동평균·변화율·집계·변동성·이상치·기온 상관·최근 추세
│   ├── plots.py              # 시각화 5장 (맑은 고딕)
│   ├── forecast.py           # 보너스 2 베이스라인 예측 (같은 요일 4주 평균, naive-7 비교)
│   ├── convert_kpx.py        # 전력거래소 시간별 CSV → 일별 합계
│   └── run.py                # 파이프라인 실행, summary.json·txt 생성
├── tests/test_analyze.py
├── images/                   # 01~05 그림, dash_01~03 대시보드 캡처, real/
└── output/                   # summary.json, summary.txt (analyzed.csv는 생성되지만 커밋 제외)
```

## 분석 요약 (시뮬레이션 데이터 기준, 자세한 근거는 REPORT.md)

| 질문 | 답 |
|---|---|
| Q1 학기 vs 방학 | 학기 일평균 1,985.6 vs 방학 1,315.0 kWh, **+51%**. 월별 집계에서 두 집단이 겹치지 않음 |
| Q2 요일·이상치 | 평일 5일은 ±1% 동일, 주말 **54%**, 공휴일 50%. (구간·날 유형·요일) 기준값 ±30% 규칙으로 이상치 6일(정전 3·행사 3) 검출, 오탐 0 |
| Q3 기온·추세 | 전체 평일로 보면 기온 효과가 음(−0.35)으로 보이지만 학기만 보면 양(+0.20). 학기 평일 냉방 +4.7%, 난방 +2.8%. 최근 7일은 추석 때문에 −19% |

## M-2와의 연결

`output/summary.json`의 `period · count · unit · metrics{total,average,max,min} · recent_7_days · trend` 필드는 M-2 "센터 운영 비서"의 `/api/data/summary` 응답과 같은 구조입니다. M-2는 이 데이터를 Firestore에 적재해 시스템 프롬프트에 주입합니다.

## 데이터 출처·라이선스

- 시뮬레이션: 이 저장소에서 생성, 제한 없음.
- 실데이터: 공공데이터포털 "한국전력거래소_시간별 전국 전력수요량"(이용허락범위 제한 없음). 상세는 `data/real/source.md`.
