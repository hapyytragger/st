import streamlit as st
import sqlite3
import os
from PIL import Image
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# --- 1. 초기 설정 ---
if not os.path.exists("avatars"):
    os.makedirs("avatars")

# 전역 공유 상태 (누가 통화 중인지 저장)
@st.cache_resource
def get_voice_users():
    return {} # { "사용자이름": "상태" }

voice_users = get_voice_users()

def get_db_connection():
    return sqlite3.connect("chat_discord.db", check_same_thread=False)

conn = get_db_connection()
cursor = conn.cursor()

# 테이블 생성
cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, avatar_path TEXT, content TEXT, timestamp TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT)")
conn.commit()

st.set_page_config(page_title="디스코드형 채팅", page_icon="🎙️", layout="wide")
st_autorefresh(interval=2000, key="global_refresh")

# WebRTC 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 2. 유저 세션 관리 ---
if "my_name" not in st.session_state:
    cursor.execute("INSERT INTO users DEFAULT VALUES")
    conn.commit()
    st.session_state.my_name = f"익명 {cursor.lastrowid}"

# --- 3. 사이드바 (채널 목록 & 프로필) ---
with st.sidebar:
    st.title("🎧 보이스 채널")
    
    # 디스코드 스타일 참가자 리스트
    st.write("🔊 **일반 음성 채널**")
    if not voice_users:
        st.caption("접속 중인 유저 없음")
    for user, status in voice_users.items():
        # 말하는 중일 때 불이 들어오는 효과
        status_icon = "🟢" if status == "speaking" else "⚪"
        st.write(f"{status_icon} {user}")
    
    st.divider()
    st.header("👤 프로필")
    custom_name = st.text_input("닉네임 변경", value=st.session_state.my_name)
    if custom_name != st.session_state.my_name:
        # 이름 변경 시 기존 통화 목록에서도 업데이트
        if st.session_state.my_name in voice_users:
            del voice_users[st.session_state.my_name]
        st.session_state.my_name = custom_name
    
    # 아바타 설정
    uploaded_file = st.file_uploader("사진", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        path = f"avatars/{st.session_state.my_name}.png"
        Image.open(uploaded_file).save(path)
        st.session_state.avatar_path = path
    else:
        st.session_state.avatar_path = f"avatars/{st.session_state.my_name}.png" if os.path.exists(f"avatars/{st.session_state.my_name}.png") else None

# --- 4. 메인 화면 ---
tab1, tab2 = st.tabs(["💬 텍스트 채팅", "🎙️ 음성 채널 입장"])

# 탭 1: 채팅 기능
with tab1:
    cursor.execute("SELECT id, name, avatar_path, content, timestamp FROM messages ORDER BY id ASC")
    for row in cursor.fetchall():
        msg_id, name, path, content, ts = row
        is_me = (name == st.session_state.my_name)
        with st.chat_message("user" if is_me else "assistant", avatar=path if path and os.path.exists(path) else None):
            col_text, col_del = st.columns([0.95, 0.05])
            col_text.write(f"**{name}** `{ts}`\n\n{content}")
            if is_me and col_del.button("X", key=f"del_{msg_id}"):
                cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                conn.commit()
                st.rerun()

    if prompt := st.chat_input("메시지 보내기..."):
        cursor.execute("INSERT INTO messages (name, avatar_path, content, timestamp) VALUES (?, ?, ?, ?)",
                       (st.session_state.my_name, st.session_state.avatar_path, prompt, datetime.now().strftime("%H:%M")))
        conn.commit()
        st.rerun()

# 탭 2: 음성 채널 입장
with tab2:
    st.subheader("🔊 음성 채널 연결")
    
    # WebRTC 상태 변화를 감지하여 전역 변수 업데이트
    ctx = webrtc_streamer(
        key="discord-voice",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if ctx.state.playing:
        voice_users[st.session_state.my_name] = "speaking"
        st.success(f"현재 '{st.session_state.my_name}'님은 음성 채널에 연결되어 있습니다.")
    else:
        # 접속 종료 시 목록에서 삭제
        if st.session_state.my_name in voice_users:
            del voice_users[st.session_state.my_name]
        st.info("START 버튼을 누르면 음성 채널에 입장합니다.")

    st.divider()
    st.caption("다른 탭을 누르거나 창을 닫으면 자동으로 연결이 종료됩니다.")
    #python3 -m streamlit run msg.py