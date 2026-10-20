import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 대시보드")

# 2. 인증키 불러오기 (Streamlit Secrets)
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("""
    **확인 및 해결 방법:**
    1. 로컬 환경: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = "발급받은키"` 형태로 저장했는지 확인하세요.
    2. Streamlit Cloud: App Settings > Secrets 메뉴에 `KOBIS_KEY`를 등록해야 합니다.
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 3. 한국 시간(KST) 기준 날짜 설정
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst).date()
max_allowed_date = now_kst - datetime.timedelta(days=1)  # 선택 가능한 최대 날짜: 어제

# 4. 달력(st.date_input)으로 조회 날짜 선택
selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (최대 어제까지 가능)",
    value=max_allowed_date,
    max_value=max_allowed_date,
    min_value=datetime.date(2003, 11, 11)
)

target_dt = selected_date.strftime("%Y%m%d")

# 5. KOBIS API 데이터 요청 함수
@st.cache_data(ttl=3600)
def fetch_box_office(key: str, dt: str):
    url = f"https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={key}&targetDt={dt}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)

data, error_msg = fetch_box_office(api_key, target_dt)

# 6. 에러 및 예외 처리
if error_msg:
    st.error("⚠️ 네트워크 요청에 실패했습니다.")
    st.warning(f"상세 에러 내용: {error_msg}")
    st.stop()

if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 에러")
    st.error("⚠️ API 호출 중 오류(faultInfo)가 발생했습니다.")
    st.warning(f"오류 메시지: {fault_msg}")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.info("💡 그날은 아직 집계 전입니다.")
    st.stop()

# 7. 데이터 전처리
df = pd.DataFrame(daily_list)

df["rank"] = df["rank"].astype(int)
df["rankInten"] = df["rankInten"].astype(int)
df["audiCnt"] = df["audiCnt"].astype(int)
df["audiAcc"] = df["audiAcc"].astype(int)
df["scrnCnt"] = df["scrnCnt"].astype(int)

# 순위 변동 기호
def format_rank_change(inten: int) -> str:
    if inten > 0:
        return f"🔺 {inten}"
    elif inten < 0:
        return f"🔹 {abs(inten)}"
    else:
        return "-"

df["순위변동"] = df["rankInten"].apply(format_rank_change)

# 100만 관객 돌파 표시 (🏆)
def add_trophy(row):
    name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"🏆 {name}"
    return name

df["표시_영화명"] = df.apply(add_trophy, axis=1)

# 8. 1위 영화 하이라이트 지표 카드 (st.metric)
top_movie = df.iloc[0]

st.subheader(f"🥇 {selected_date.strftime('%Y년 %m월 %d일')} Box Office 1위")

m_col1, m_col2, m_col3 = st.columns(3)

with m_col1:
    st.metric(
        label="🎬 1위 영화명",
        value=top_movie["표시_영화명"]
    )

with m_col2:
    st.metric(
        label="🍿 당일 관객수",
        value=f"{top_movie['audiCnt']:,} 명",
        delta=f"전일 대비 {top_movie['순위변동']}" if top_movie["rankInten"] != 0 else "순위 유지"
    )

with m_col3:
    st.metric(
        label="👥 누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )

st.markdown("---")

# 9. TOP 5 영화 요약 카드
st.subheader("⭐ TOP 5 영화 요약")

top_5_movies = df.head(5)
cols = st.columns(5)

for idx, (_, movie) in enumerate(top_5_movies.iterrows()):
    with cols[idx]:
        st.info(f"**{movie['rank']}위. {movie['표시_영화명']}**\n\n- 관객수: {movie['audiCnt']:,}명\n- 개봉일: {movie['openDt']}")

st.markdown("---")

# 10. 관객수 상위 5개 영화 막대그래프
st.subheader("📊 관객수 상위 5개 영화 비교")
top_5_df = df.head(5)[["표시_영화명", "audiCnt"]].set_index("표시_영화명")
st.bar_chart(top_5_df, y="audiCnt")

st.markdown("---")

# 11. 전체 박스오피스 순위표 출력
st.subheader("📋 전체 박스오피스 순위 (1위 ~ 10위)")

display_df = df[["rank", "순위변동", "표시_영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "전일대비", "영화명", "개봉일", "당일 관객수", "누적 관객수", "스크린수"]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "당일 관객수": st.column_config.NumberColumn("당일 관객수", format="%d명"),
        "누적 관객수": st.column_config.NumberColumn("누적 관객수", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개"),
    }
)
