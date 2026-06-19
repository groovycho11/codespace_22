import streamlit as st
from supabase import create_client
from groq import Groq
import requests
import json
import re

# =========================================================================
# [설정] 와이드 레이아웃 (최상단 필수)
# =========================================================================
st.set_page_config(
    page_title="Jazz Lick Database",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================================
# 1. Supabase 연결 설정
# =========================================================================
SUPABASE_URL = "https://bvjesfuuxssuywcaiyxd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2amVzZnV1eHNzdXl3Y2FpeXhkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM4OTg2MTAsImV4cCI6MjA4OTQ3NDYxMH0.lgn-g6jy35J4gntd1BnokJ27K7_Jk4Ye9GrFmylnJO8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================================
# 2. API 키 설정
#    ↓↓↓ 여기에 본인의 키를 입력하세요 ↓↓↓
# =========================================================================
GROQ_API_KEY      = "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"       # Groq API 키
YOUTUBE_API_KEY   = "AIzaSyAEGleTi8VPI9gaZ3_Zx2kw_dDSnuMW5zk"    # YouTube Data API v3 키

groq_ready = GROQ_API_KEY != "YOUR_GROQ_API_KEY_HERE"
yt_ready   = YOUTUBE_API_KEY != "YOUR_YOUTUBE_API_KEY_HERE"
ai_ready   = groq_ready and yt_ready

# Groq 클라이언트 전역 초기화
groq_client = Groq(api_key=GROQ_API_KEY) if groq_ready else None


# =========================================================================
# 3. 공통 유틸 함수
# =========================================================================
def convert_time_to_seconds(time_input):
    """다양한 형태의 시간 입력을 초(seconds) 단위 정수로 변환합니다."""
    if not time_input or time_input == '-':
        return 0
    time_str = str(time_input).strip()
    try:
        if '.' in time_str and ':' not in time_str:
            parts = time_str.split('.')
            minutes = int(parts[0])
            seconds_str = parts[1]
            seconds = int(seconds_str) * 10 if len(seconds_str) == 1 else int(seconds_str[:2])
            return minutes * 60 + seconds

        if '분' in time_str or '초' in time_str:
            minutes, seconds = 0, 0
            match_min = re.search(r'(\d+)\s*분', time_str)
            match_sec = re.search(r'(\d+)\s*초', time_str)
            if match_min: minutes = int(match_min.group(1))
            if match_sec: seconds = int(match_sec.group(1))
            return minutes * 60 + seconds

        if ':' in time_str:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 2: return parts[0] * 60 + parts[1]
            elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]

        if time_str.isdigit():
            return int(time_str)
    except Exception:
        return 0
    return 0


def extract_youtube_id(url: str):
    """유튜브 URL에서 video_id를 추출합니다."""
    if not url:
        return None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[\?&]|$)',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'embed\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def render_youtube_embed(yt_url: str, start: str):
    """유튜브 영상을 임베드로 렌더링합니다."""
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        st.warning("유효하지 않은 유튜브 링크입니다.")
        st.link_button("📺 원본 링크 열기", yt_url, use_container_width=True)
        return

    start_seconds = convert_time_to_seconds(start)
    embed_url = f"https://www.youtube.com/embed/{video_id}?rel=0"
    if start_seconds > 0:
        embed_url += f"&start={start_seconds}"

    st.components.v1.html(
        f'<iframe width="100%" height="315" src="{embed_url}" '
        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
        f'encrypted-media; gyroscope; picture-in-picture" '
        f'allowfullscreen referrerpolicy="strict-origin-when-cross-origin" '
        f'style="border-radius:12px;"></iframe>',
        height=325
    )
    button_url = f"https://www.youtube.com/watch?v={video_id}"
    if start_seconds > 0:
        button_url += f"&t={start_seconds}s"
    st.link_button(
        f"▶️ YouTube에서 [{start}] 구간 시청하기",
        button_url,
        use_container_width=True
    )


# =========================================================================
# 4. 데이터 조회 함수
# =========================================================================
def get_jazz_data(filters):
    query = (
        supabase.table("lick_timestamps")
        .select(
            "lick_id, start_time, end_time, play_type, chord_progression, is_ai_generated, "
            "jazz_videos!inner(video_id, title, youtube_url, bpm, rhythm_type, "
            "performers!inner(performer_id, name, instrument))"
        )
    )
    if filters.get('title'):
        query = query.filter("jazz_videos.title", "ilike", f"%{filters['title']}%")
    if filters.get('chord'):
        query = query.ilike("chord_progression", f"%{filters['chord']}%")
    if filters.get('performer'):
        query = query.filter("jazz_videos.performers.name", "ilike", f"%{filters['performer']}%")
    if filters.get('bpm'):
        target_bpm = filters['bpm']
        query = (
            query.filter("jazz_videos.bpm", "gte", target_bpm - 10)
                 .filter("jazz_videos.bpm", "lte", target_bpm + 10)
        )
    if filters.get('rhythm_type'):
        query = query.filter("jazz_videos.rhythm_type", "eq", filters['rhythm_type'])
    if filters.get('play_type'):
        query = query.eq("play_type", filters['play_type'])
    return query.execute()


# =========================================================================
# 5. Groq AI 분석 함수
# =========================================================================
def analyze_with_groq(raw_text: str) -> dict:
    """Groq(Llama)으로 텍스트를 구조화된 dict로 변환합니다."""
    client = groq_client

    prompt = f"""당신은 재즈 연주 데이터베이스 등록 전문 AI입니다.
아래 텍스트에서 정보를 추출하세요.

반드시 아래 JSON 형식만 출력하세요. 마크다운(```)이나 설명 텍스트는 절대 포함하지 마세요.

{{
    "performer_name": "연주자 이름 (없으면 None)",
    "instrument": "악기명 (예: Flute, Piano, Saxophone, Drums 등, 유추 불가시 None)",
    "video_title": "곡 제목 또는 영상 타이틀",
    "youtube_url": "본문에 실제 유튜브 주소가 있다면 추출, 없으면 None",
    "rhythm_type": "Swing / Mambo / Bossa Nova / Funk 중 하나, 유추 불가능하면 Swing",
    "bpm": 숫자정수 (모르면 0),
    "play_type": "Solo / Comping / Trading 중 하나, 기본값 Solo",
    "start_time": "분:초 형태 (예: 4:30), 없으면 0:00",
    "end_time": "분:초 형태 (예: 4:40), 없으면 0:00",
    "chord_progression": "코드진행 (예: ii-V-I), 없으면 None"
}}

[분석할 텍스트]:
{raw_text}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    clean = re.sub(r'```json|```', '', response.choices[0].message.content).strip()
    return json.loads(clean)


# =========================================================================
# 6. YouTube Data API로 실제 영상 URL 검색
# =========================================================================
def search_youtube_url(performer: str, title: str) -> str:
    """YouTube Data API v3로 연주자 + 곡 제목 검색 후 첫 번째 영상 URL 반환."""
    query = f"{performer} {title}".strip()
    if not query:
        return None

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY
            },
            timeout=10
        )
        data = resp.json()
        items = data.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        st.warning(f"YouTube 검색 중 오류: {e}")
    return None


# =========================================================================
# 7. Supabase 위키형 저장 함수
# =========================================================================
def save_to_supabase(d: dict, youtube_url_override: str = None) -> bool:
    # 최종 YouTube URL 결정
    final_url = (
        youtube_url_override.strip()
        if youtube_url_override and youtube_url_override.strip()
        else (d.get('youtube_url') or "")
    )
    if final_url == "None":
        final_url = ""

    # ── [1단계] Performers ──────────────────────────────────────────────
    p_name = (d.get('performer_name') or "").strip()
    if not p_name or p_name == "None":
        p_name = "미상"

    p_check = supabase.table("performers").select("performer_id").eq("name", p_name).execute()
    if p_check.data:
        performer_id = p_check.data[0]['performer_id']
        st.caption(f"ℹ️ 기존 연주자 재사용: **{p_name}** (performer_id: {performer_id})")
    else:
        instrument = d.get('instrument') or "-"
        if instrument == "None": instrument = "-"
        p_ins = supabase.table("performers").insert({
            "name": p_name,
            "instrument": instrument
        }).execute()
        performer_id = p_ins.data[0]['performer_id']
        st.caption(f"✨ 새 연주자 등록: **{p_name}** (performer_id: {performer_id})")

    # ── [2단계] Jazz Videos ─────────────────────────────────────────────
    v_title = (d.get('video_title') or "").strip()
    if not v_title or v_title == "None":
        v_title = "제목 미상"

    v_check = supabase.table("jazz_videos").select("video_id").eq("title", v_title).execute()
    if v_check.data:
        video_id = v_check.data[0]['video_id']
        if final_url:
            supabase.table("jazz_videos").update({"youtube_url": final_url}).eq("video_id", video_id).execute()
            st.caption(f"🔗 기존 영상 URL 업데이트: **{v_title}**")
        else:
            st.caption(f"ℹ️ 기존 영상 재사용: **{v_title}**")
    else:
        bpm_val = 0
        try: bpm_val = int(d.get('bpm', 0))
        except: pass

        v_ins = supabase.table("jazz_videos").insert({
            "title": v_title,
            "youtube_url": final_url,
            "rhythm_type": d.get('rhythm_type', 'Swing'),
            "bpm": bpm_val,
            "performer_id": performer_id
        }).execute()
        video_id = v_ins.data[0]['video_id']
        st.caption(f"✨ 새 영상 등록: **{v_title}** (video_id: {video_id})")

    # ── [3단계] Lick Timestamps ─────────────────────────────────────────
    chord = d.get('chord_progression') or "None"
    supabase.table("lick_timestamps").insert({
        "video_id": video_id,
        "start_time": d.get('start_time', '0:00'),
        "end_time": d.get('end_time', '0:00'),
        "play_type": d.get('play_type', 'Solo'),
        "chord_progression": chord,
        "is_ai_generated": True
    }).execute()
    return True


# =========================================================================
# 8. 메인 탭 구성
# =========================================================================
main_tab1, main_tab2 = st.tabs(["🔍 재즈 릭 탐색 대시보드", "🤖 AI 위키형 자료 등록기"])


# ─────────────────────────────────────────────────────────────────────────
# TAB 1: 탐색 대시보드
# ─────────────────────────────────────────────────────────────────────────
with main_tab1:
    st.sidebar.header("🔍 정밀 탐색 필터")
    sidebar_filters = {
        'title':       st.sidebar.text_input("곡 제목"),
        'performer':   st.sidebar.text_input("연주자"),
        'bpm':         st.sidebar.number_input("BPM (±10 자동계산)", value=0),
        'rhythm_type': st.sidebar.selectbox("리듬", ["전체", "Swing", "Mambo", "Bossa Nova", "Funk"]),
        'chord':       st.sidebar.text_input("코드 진행 (예: ii-V-I)"),
        'play_type':   st.sidebar.selectbox("연주 형태", ["전체", "Solo", "Comping", "Trading"])
    }
    sidebar_filters = {
        k: v for k, v in sidebar_filters.items()
        if v and v != "전체" and v != 0
    }

    if st.sidebar.button("검색하기"):
        try:
            results = get_jazz_data(sidebar_filters)
            if results.data:
                st.success(f"🎉 {len(results.data)}개의 결과를 찾았습니다.")
                st.write("")
                for item in results.data:
                    video     = item.get('jazz_videos') or {}
                    performer = video.get('performers') or {}
                    start     = item.get('start_time', '-')
                    end       = item.get('end_time', '-')
                    yt_url    = (video.get('youtube_url') or '').strip()
                    is_ai     = item.get('is_ai_generated', False)

                    if yt_url:
                        col1, col2 = st.columns([1, 1], gap="large")
                    else:
                        col1 = st.container()

                    with col1:
                        ai_badge = " 🤖 AI 등록" if is_ai else ""
                        st.subheader(f"🎵 {video.get('title', 'Unknown')}{ai_badge}")
                        st.markdown(f"**연주 형태:** `{item.get('play_type', '-')}`")
                        st.markdown(f"👤 **연주자:** {performer.get('name', '미상')} ({performer.get('instrument', '-')})")
                        st.markdown(f"⏱️ **구간:** `{start}` ~ `{end}`")
                        st.markdown(f"🥁 **리듬 / BPM:** {video.get('rhythm_type', '-')} | `{video.get('bpm', '-')}` BPM")
                        st.markdown(f"🎹 **코드 진행:** `{item.get('chord_progression', '-')}`")

                    if yt_url:
                        with col2:
                            st.caption("📺 연주 영상 감상")
                            render_youtube_embed(yt_url, start)
                    st.divider()
            else:
                st.warning("일치하는 결과가 없습니다.")
        except Exception as e:
            st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")


# ─────────────────────────────────────────────────────────────────────────
# TAB 2: AI 위키형 자료 등록기
# ─────────────────────────────────────────────────────────────────────────
with main_tab2:
    st.header("🤖 AI 기반 위키형 데이터 등록")
    st.markdown(
        "연주자 이름과 곡 제목만 입력하면, AI가 정보를 구조화하고 "
        "YouTube에서 실제 영상 링크를 자동으로 찾아드립니다."
    )

    # API 키 상태 표시
    col_a, col_b = st.columns(2)
    with col_a:
        if groq_ready:
            st.success("✅ Groq API 연결됨")
        else:
            st.error("❌ GROQ_API_KEY 미입력")
    with col_b:
        if yt_ready:
            st.success("✅ YouTube API 연결됨")
        else:
            st.error("❌ YOUTUBE_API_KEY 미입력")

    st.write("")

    raw_text_input = st.text_area(
        "📝 재즈 연주 정보 입력 (자유 형식)",
        height=150,
        placeholder=(
            "예시 1 (간단): phily joe jones의 confirmation 솔로 추가해줘\n\n"
            "예시 2 (상세): gyoungdun 플루트 연주자의 Little Cubana. "
            "라틴 리듬, BPM 210, 구간 4:30~4:40\n\n"
            "예시 3 (URL 직접): Miles Davis So What https://youtu.be/xxxx"
        )
    )

    if st.button("🪄 AI 분석 + YouTube 자동 검색", disabled=not ai_ready):
        if not raw_text_input.strip():
            st.warning("분석할 텍스트를 먼저 입력해 주세요.")
        else:
            with st.spinner("① Groq AI가 정보를 구조화하고 있습니다..."):
                try:
                    parsed = analyze_with_groq(raw_text_input)
                    st.session_state['pending_lick_data'] = parsed
                    st.success("🎉 AI 분석 완료!")
                    st.json(parsed)
                except Exception as e:
                    st.error(f"Groq 분석 중 오류: {e}")
                    st.stop()

            # YouTube URL이 없으면 자동 검색
            if not parsed.get('youtube_url') or parsed['youtube_url'] == 'None':
                performer = parsed.get('performer_name', '') or ''
                title     = parsed.get('video_title', '') or ''
                if performer == 'None': performer = ''
                if title == 'None': title = ''

                with st.spinner(f"② YouTube에서 '{performer} {title}' 영상을 검색 중..."):
                    found_url = search_youtube_url(performer, title)
                    if found_url:
                        parsed['youtube_url'] = found_url
                        st.session_state['pending_lick_data'] = parsed
                        st.success(f"🎬 YouTube 영상 자동 발견: {found_url}")
                    else:
                        st.warning("YouTube에서 자동으로 영상을 찾지 못했습니다. 아래에서 직접 입력해 주세요.")

    # ── YouTube URL 확인 및 최종 등록 ────────────────────────────────────
    if 'pending_lick_data' in st.session_state:
        d = st.session_state['pending_lick_data']
        st.divider()
        st.markdown("### ✏️ 데이터 직접 수정")
        st.caption("저장 전에 AI가 분석한 값을 직접 수정할 수 있습니다.")

        # ── 필드별 직접 수정 UI ──────────────────────────────────────────
        col1, col2 = st.columns(2)
        with col1:
            edit_performer = st.text_input("👤 연주자명", value=d.get('performer_name', '') or '')
            edit_instrument = st.text_input("🎸 악기", value=d.get('instrument', '') or '')
            edit_title = st.text_input("🎵 곡 제목", value=d.get('video_title', '') or '')
            edit_rhythm = st.selectbox("🥁 리듬", ["Swing", "Mambo", "Bossa Nova", "Funk"],
                index=["Swing", "Mambo", "Bossa Nova", "Funk"].index(d.get('rhythm_type', 'Swing'))
                if d.get('rhythm_type') in ["Swing", "Mambo", "Bossa Nova", "Funk"] else 0)
        with col2:
            edit_bpm = st.number_input("🎚️ BPM", value=int(d.get('bpm', 0) or 0), min_value=0)
            edit_play_type = st.selectbox("🎹 연주 형태", ["Solo", "Comping", "Trading"],
                index=["Solo", "Comping", "Trading"].index(d.get('play_type', 'Solo'))
                if d.get('play_type') in ["Solo", "Comping", "Trading"] else 0)
            edit_start = st.text_input("⏱️ 시작 시간 (예: 2:30)", value=d.get('start_time', '0:00') or '0:00')
            edit_end = st.text_input("⏱️ 종료 시간 (예: 2:45)", value=d.get('end_time', '0:00') or '0:00')
        edit_chord = st.text_input("🎼 코드 진행 (예: ii-V-I)", value=d.get('chord_progression', 'None') or 'None')

        # 수정된 값을 세션에 반영
        d_edited = {
            'performer_name': edit_performer,
            'instrument': edit_instrument,
            'video_title': edit_title,
            'youtube_url': d.get('youtube_url', 'None'),
            'rhythm_type': edit_rhythm,
            'bpm': edit_bpm,
            'play_type': edit_play_type,
            'start_time': edit_start,
            'end_time': edit_end,
            'chord_progression': edit_chord
        }

        st.divider()
        st.markdown("### 🔗 YouTube 링크 확인")

        ai_url = d.get('youtube_url', 'None') or 'None'

        if ai_url and ai_url != 'None':
            st.success(f"✅ YouTube URL: {ai_url}")
            user_url_input = st.text_input("URL 수정 가능", value=ai_url)
        else:
            user_url_input = st.text_input(
                "YouTube URL 직접 입력",
                placeholder="https://www.youtube.com/watch?v=..."
            )

        # URL 미리보기 (임베드 차단 영상 대비 썸네일 fallback)
        preview_url = (user_url_input or ai_url or '').strip()
        if preview_url and preview_url != 'None':
            vid_id = extract_youtube_id(preview_url)
            if vid_id:
                st.caption("📺 미리보기")
                embed_html = f"""
                <div id="preview-wrap" style="position:relative;width:100%;padding-bottom:56.25%;border-radius:10px;overflow:hidden;background:#000;">
                  <iframe id="yt-frame" width="100%" height="100%"
                    style="position:absolute;top:0;left:0;border-radius:10px;"
                    src="https://www.youtube.com/embed/{vid_id}?rel=0"
                    frameborder="0" allowfullscreen
                    onerror="this.style.display='none';document.getElementById('yt-thumb').style.display='block';">
                  </iframe>
                  <a id="yt-thumb" href="https://www.youtube.com/watch?v={vid_id}" target="_blank"
                    style="display:none;position:absolute;top:0;left:0;width:100%;height:100%;text-decoration:none;">
                    <img src="https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                      style="width:100%;height:100%;object-fit:cover;border-radius:10px;" />
                    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                      background:rgba(0,0,0,0.7);border-radius:50%;width:64px;height:64px;
                      display:flex;align-items:center;justify-content:center;">
                      <span style="color:white;font-size:28px;">▶</span>
                    </div>
                  </a>
                </div>
                <script>
                  var frame = document.getElementById('yt-frame');
                  var thumb = document.getElementById('yt-thumb');
                  frame.addEventListener('load', function() {{
                    try {{
                      if (frame.contentDocument && frame.contentDocument.title === '') {{
                        frame.style.display = 'none';
                        thumb.style.display = 'block';
                      }}
                    }} catch(e) {{}}
                  }});
                  setTimeout(function() {{
                    try {{
                      var doc = frame.contentDocument || frame.contentWindow.document;
                      if (!doc || doc.title === '') {{
                        frame.style.display = 'none';
                        thumb.style.display = 'block';
                      }}
                    }} catch(e) {{
                      // 크로스 오리진이면 썸네일로 대체
                      frame.style.display = 'none';
                      thumb.style.display = 'block';
                    }}
                  }}, 3000);
                </script>
                """
                st.components.v1.html(embed_html, height=320)
                st.link_button("▶️ YouTube에서 직접 보기", f"https://www.youtube.com/watch?v={vid_id}", use_container_width=True)
            else:
                st.warning("유효하지 않은 YouTube URL 형식입니다.")

        st.info("✅ 중복 연주자·영상은 자동 감지하여 기존 레코드에 연결합니다.")

        if st.button("🚀 Supabase에 최종 저장", type="primary"):
            try:
                d_edited['youtube_url'] = user_url_input if user_url_input else d.get('youtube_url', '')
                with st.spinner("데이터베이스에 저장 중..."):
                    save_to_supabase(d_edited, youtube_url_override=user_url_input)
                st.balloons()
                st.success("🏅 저장 완료! 탐색 탭에서 바로 검색해 보세요.")
                del st.session_state['pending_lick_data']
            except Exception as e:
                st.error(f"Supabase 저장 중 오류 발생: {e}")