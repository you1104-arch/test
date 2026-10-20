import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# 1. 페이지 기본 설정 (제목, 레이아웃 등)
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")

# 2. 인증키 불러오기 (Streamlit Secrets 활용)
# secrets.toml 파일이나 Streamlit Cloud의 Secrets 설정에서 KOBIS_KEY를 가져옵니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("""
    **확인 및 해결 방법:**
    1. 로컬 환경: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = "발급받은키"` 형태로 저장했는지 확인하세요.
    2. Streamlit Cloud: App Settings > Secrets 메뉴에 `KOBIS_KEY`를 등록해야 합니다.
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 3. 한국 시간(KST) 기준으로 '어제' 날짜 계산하기
# 서버 시계가 해외 기준(UTC 등)이어도 한국 표준시(Asia/Seoul)를 기준으로 어제 날짜를 구합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday = now_kst - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")  # YYYYMMDD 형태로 변환 (예: 20261019)

# 사용자에게 조회 대상 날짜 표시
formatted_date = yesterday.strftime("%Y년 %m월 %d일")
st.caption(f"📅 기준 날짜: {formatted_date}")

# 4. KOBIS API 데이터 요청 함수
@st.cache_data(ttl=3600)  # 1시간 동안 API 호출 결과를 캐싱하여 요청 횟수 절약
def fetch_box_office(key: str, dt: str):
    url = f"https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={key}&targetDt={dt}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # HTTP status code 오류 검사 (4xx, 5xx)
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)

# API 데이터 불러오기
data, error_msg = fetch_box_office(api_key, target_dt)

# 5. 에러 및 예외 처리
if error_msg:
    st.error("⚠️ 네트워크 요청에 실패했습니다.")
    st.warning(f"상세 에러 내용: {error_msg}")
    st.info("💡 **확인사항:** 인터넷 연결 상태를 확인하거나 API 서비스 장애 여부를 검토하세요.")
    st.stop()

# KOBIS API는 인증키가 틀렸을 때도 HTTP 200 응답과 함께 'faultInfo' 구조를 반환합니다.
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 에러")
    st.error("⚠️ API 호출 중 오류(faultInfo)가 발생했습니다.")
    st.warning(f"오류 메시지: {fault_msg}")
    st.info("""
    💡 **확인사항:**
    - 등록된 `KOBIS_KEY`가 올바른지 확인하세요.
    - 영화진흥위원회 오픈API 포털에서 인증키의 일일 요청 제한 초과 여부를 확인하세요.
    """)
    st.stop()

# 응답 데이터에서 영화 목록 추출
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어있는 경우
if not daily_list:
    st.warning("⚠️ 조회된 박스오피스 영화 목록이 없습니다.")
    st.info("""
    💡 **확인사항:**
    - 해당 날짜의 박스오피스 집계가 아직 완료되지 않았을 수 있습니다.
    - 데이터가 제공되는 서버 시스템 점검 시간인지 확인해 보세요.
    """)
    st.stop()

# 6. 데이터 전처리 (판다스 데이터프레임 변환 및 숫자형 데이터 형변환)
df = pd.DataFrame(daily_list)

# KOBIS API의 숫자 데이터는 문자열 형태이므로 숫자형(int)으로 정제합니다.
df["rank"] = df["rank"].astype(int)
df["audiCnt"] = df["audiCnt"].astype(int)
df["audiAcc"] = df["audiAcc"].astype(int)
df["scrnCnt"] = df["scrnCnt"].astype(int)

# 7. 1위 영화 핵심 지표 카드 (st.metric) 출력
top_movie = df.iloc[0]

st.subheader("🥇 어제의 1위 영화")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="🎬 영화명",
        value=top_movie["movieNm"]
    )

with col2:
    # 전일 대비 증감(rankInten)을 delta 표시
    rank_inten = int(top_movie.get("rankInten", 0))
    st.metric(
        label="🍿 어제 관객수",
        value=f"{top_movie['audiCnt']:,} 명",
        delta=f"{rank_inten} 순위 변동" if rank_inten != 0 else "순위 유지"
    )

with col3:
    st.metric(
        label="👥 누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )

st.markdown("---")

# 8. 관객수 상위 5개 영화 막대그래프
st.subheader("📊 관객수 상위 5개 영화")
top_5_df = df.head(5)[["movieNm", "audiCnt"]].set_index("movieNm")
# Streamlit 기본 차트 활용 (x축: 관객수, y축: 영화명)
st.bar_chart(top_5_df, y="audiCnt")

st.markdown("---")

# 9. 전체 박스오피스 순위표 출력
st.subheader("📋 박스오피스 순위 (1위 ~ 10위)")

# 표에 보여줄 컬럼 선택 및 컬럼명 한국어 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "어제 관객수", "누적 관객수", "스크린수"]

# 숫자 표기 가독성을 높이기 위해 서식 지정 후 보여주기
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "어제 관객수": st.column_config.NumberColumn("어제 관객수", format="%d명"),
        "누적 관객수": st.column_config.NumberColumn("누적 관객수", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개"),
    }
)
