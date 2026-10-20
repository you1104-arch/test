import datetime
import requests
import pandas as pd
import pytz
import urllib.parse
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 & 영화 포스터 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 & 영화 포스터 대시보드")

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

# 6. 영화별 동적 포스터 카드 생성 함수 (SVG 기반, 한글 100% 지원 & 중복 방지)
def render_movie_card(rank: int, movie_name: str, audience: int):
    colors = [
        ("#1A202C", "#2D3748"),  # 1위: 다크 슬레이트
        ("#1E3A8A", "#3B82F6"),  # 2위: 블루
        ("#065F46", "#10B981"),  # 3위: 에메랄드
        ("#831843", "#EC4899"),  # 4위: 핑크/로즈
        ("#312E81", "#6366F1"),  # 5위: 인디고
    ]
    bg_start, bg_end = colors[(rank - 1) % len(colors)]
    
    # SVG 코드로 영화 제목과 순위가 디자인된 카드 생성
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="320" viewBox="0 0 200 300">
        <defs>
            <linearGradient id="grad{rank}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{bg_start};stop-opacity:1" />
                <stop offset="100%" style="stop-color:{bg_end};stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="200" height="300" rx="12" fill="url(#grad{rank})" />
        <circle cx="35" cy="35" r="20" fill="rgba(255, 255, 255, 0.2)" />
        <text x="35" y="42" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{rank}</text>
        <text x="100" y="140" font-family="'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" font-size="15" font-weight="bold" fill="#FFFFFF" text-anchor="middle">
            <tspan x="100" dy="0">{movie_name[:10]}</tspan>
            <tspan x="100" dy="20">{movie_name[10:20]}</tspan>
        </text>
        <rect x="20" y="230" width="160" height="1" fill="rgba(255,255,255,0.3)" />
        <text x="100" y="255" font-family="Arial, sans-serif" font-size="11" fill="rgba(255,255,255,0.8)" text-anchor="middle">관객수</text>
        <text x="100" y="275" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#FFD700" text-anchor="middle">{audience:,}명</text>
    </svg>
    """
    
    # Data URI 방식으로 SVG 이미지 전달
    encoded_svg = urllib.parse.quote(svg_code)
    return f"data:image/svg+xml;utf8,{encoded_svg}"

data, error_msg = fetch_box_office(api_key, target_dt)

# 7. 에러 및 예외 처리
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

# 8. 데이터 전처리
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

# 9. 1위 영화 하이라이트
top_movie = df.iloc[0]

st.subheader(f"🥇 {selected_date.strftime('%Y년 %m월 %d일')} Box Office 1위")

col_left, col_right = st.columns([1, 2])

with col_left:
    top_card_svg = render_movie_card(1, top_movie["movieNm"], top_movie["audiCnt"])
    st.image(top_card_svg, use_container_width=True)

with col_right:
    st.markdown(f"### **{top_movie['표시_영화명']}**")
    st.caption(f"개봉일: {top_movie['openDt']} | 스크린 수: {top_movie['scrnCnt']:,}개")
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(
            label="🍿 당일 관객수",
            value=f"{top_movie['audiCnt']:,} 명",
            delta=f"전일 대비 {top_movie['순위변동']}" if top_movie["rankInten"] != 0 else "순위 유지"
        )
    with m_col2:
        st.metric(
            label="👥 누적 관객수",
            value=f"{top_movie['audiAcc']:,} 명"
        )

st.markdown("---")

# 10. TOP 5 영화 포스터 갤러리
st.subheader("🖼️ TOP 5 영화 포스터 카드")

top_5_movies = df.head(5)
cols = st.columns(5)

for idx, (_, movie) in enumerate(top_5_movies.iterrows()):
    with cols[idx]:
        card_svg = render_movie_card(movie["rank"], movie["movieNm"], movie["audiCnt"])
        st.image(card_svg, use_container_width=True)
        st.markdown(f"**{movie['rank']}위. {movie['표시_영화명']}**")

st.markdown("---")

# 11. 관객수 상위 5개 영화 막대그래프
st.subheader("📊 관객수 상위 5개 영화 비교")
top_5_df = df.head(5)[["표시_영화명", "audiCnt"]].set_index("표시_영화명")
st.bar_chart(top_5_df, y="audiCnt")

st.markdown("---")

# 12. 전체 박스오피스 순위표 출력
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
