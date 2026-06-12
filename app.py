import streamlit as st
import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from src.downloader import get_video_info, download_audio, download_video
from src.transcriber import transcribe
from src.snapshot import extract_snapshots
from src.summarizer import generate_summary, format_transcript

load_dotenv()

st.set_page_config(
    page_title="VTT - 動画文字起こしツール",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 VTT — 動画文字起こし & プレゼン資料作成")
st.caption("YouTube / Newspicks の動画を文字起こしして、プレゼン用サマリを生成します")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 設定")

    model_size = st.selectbox(
        "Whisperモデル",
        ["tiny", "base", "small", "medium", "large-v3"],
        index=3,
        help="大きいほど精度が高いが処理が遅い。medium が推奨（初回のみモデルDLあり）",
    )

    language = st.selectbox(
        "言語",
        [("日本語", "ja"), ("English", "en"), ("自動検出", None)],
        format_func=lambda x: x[0],
        index=0,
    )

    st.divider()

    enable_snapshots = st.toggle("スナップショット取得", value=True)
    snapshot_interval = st.slider(
        "スナップショット間隔（秒）",
        min_value=15,
        max_value=300,
        value=60,
        step=15,
        disabled=not enable_snapshots,
    )

    st.divider()

    api_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Claude によるサマリ生成に使用。未入力の場合はスキップ",
    )

    st.divider()

    cookie_file = st.file_uploader(
        "Cookie ファイル（Newspicks 有料会員など）",
        type=["txt"],
        help="Netscape 形式の cookie ファイル。yt-dlp の --cookies オプションと同等",
    )

# ── Main ──────────────────────────────────────────────────────────────────────
url = st.text_input(
    "動画 URL",
    placeholder="https://www.youtube.com/watch?v=...  または  https://newspicks.com/...",
)

start_btn = st.button("▶ 処理開始", type="primary", disabled=not url)

if start_btn and url:
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = Path("output") / session_id
    work_dir.mkdir(parents=True, exist_ok=True)

    cookiefile_path = None
    if cookie_file:
        cookiefile_path = str(work_dir / "cookies.txt")
        (work_dir / "cookies.txt").write_bytes(cookie_file.read())

    lang_code = language[1]  # None | "ja" | "en"
    results = {}

    # ── Step 1: 動画情報 ──────────────────────────────────────────────────────
    with st.status("動画情報を取得中...", expanded=True) as status:
        try:
            info = get_video_info(url, cookiefile_path)
            results["info"] = info
            duration_str = (
                f"{info['duration'] // 3600}時間{(info['duration'] % 3600) // 60}分"
                if info["duration"] >= 3600
                else f"{info['duration'] // 60}分{info['duration'] % 60}秒"
            )
            st.write(f"**{info['title']}**")
            st.write(f"投稿者: {info['uploader']} | 長さ: {duration_str}")
            status.update(label="✅ 動画情報取得完了", state="complete")
        except Exception as e:
            status.update(label=f"❌ 動画情報取得失敗: {e}", state="error")
            st.stop()

    # ── Step 2: 音声ダウンロード ──────────────────────────────────────────────
    with st.status("音声をダウンロード中...", expanded=False) as status:
        try:
            audio_path = download_audio(url, work_dir / "audio", cookiefile_path)
            results["audio_path"] = str(audio_path)
            status.update(label="✅ 音声ダウンロード完了", state="complete")
        except Exception as e:
            status.update(label=f"❌ ダウンロード失敗: {e}", state="error")
            st.stop()

    # ── Step 3: 文字起こし ────────────────────────────────────────────────────
    with st.status(f"文字起こし中（Whisper {model_size}）...", expanded=True) as status:
        st.caption("初回はモデルのダウンロードが発生します（数分かかる場合があります）")
        progress_bar = st.progress(0.0, text="処理中...")

        def on_progress(current: float, total: float):
            pct = min(current / total, 1.0) if total else 0.0
            m, s = divmod(int(current), 60)
            progress_bar.progress(pct, text=f"{m:02d}:{s:02d} / {int(total)//60:02d}:{int(total)%60:02d}")

        try:
            segments = transcribe(audio_path, model_size, lang_code, on_progress)
            results["segments"] = segments
            total_chars = sum(len(s["text"]) for s in segments)
            progress_bar.progress(1.0, text="完了")
            status.update(
                label=f"✅ 文字起こし完了（{total_chars:,} 文字 / {len(segments)} セグメント）",
                state="complete",
            )
        except Exception as e:
            status.update(label=f"❌ 文字起こし失敗: {e}", state="error")
            st.stop()

    # ── Step 4: スナップショット ──────────────────────────────────────────────
    snapshot_list: list[tuple[int, Path]] = []
    if enable_snapshots:
        with st.status("動画をダウンロード中（スナップショット用）...", expanded=False) as status:
            try:
                video_path = download_video(url, work_dir / "video", cookiefile_path)
                status.update(label="✅ 動画ダウンロード完了", state="complete")
            except Exception as e:
                status.update(label=f"⚠️ 動画ダウンロード失敗（スナップショットをスキップ）: {e}", state="error")
                video_path = None

        if video_path:
            with st.status("スナップショットを抽出中...", expanded=False) as snap_status:
                try:
                    snapshot_list = extract_snapshots(
                        video_path, work_dir / "snapshots", snapshot_interval
                    )
                    snap_status.update(
                        label=f"✅ スナップショット {len(snapshot_list)} 枚を抽出", state="complete"
                    )
                except Exception as e:
                    snap_status.update(label=f"⚠️ スナップショット抽出失敗: {e}", state="error")

    results["snapshots"] = [(ts, str(p)) for ts, p in snapshot_list]

    # ── Step 5: サマリ生成 ────────────────────────────────────────────────────
    summary_md = ""
    if api_key:
        with st.status("Claude API でサマリを生成中...", expanded=False) as status:
            try:
                summary_md = generate_summary(
                    title=info["title"],
                    uploader=info["uploader"],
                    duration=float(info["duration"]),
                    segments=segments,
                    api_key=api_key,
                )
                results["summary"] = summary_md
                status.update(label="✅ サマリ生成完了", state="complete")
            except Exception as e:
                status.update(label=f"⚠️ サマリ生成失敗: {e}", state="error")
    else:
        st.info("Anthropic API Key が未設定のため、サマリ生成をスキップしました")

    # ── ファイル保存 ──────────────────────────────────────────────────────────
    transcript_path = work_dir / "transcript.md"
    transcript_path.write_text(
        f"# {info['title']}\n\n"
        f"- URL: {url}\n"
        f"- 投稿者: {info['uploader']}\n\n"
        "## 全文テキスト\n\n"
        + format_transcript(segments),
        encoding="utf-8",
    )

    if summary_md:
        (work_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    (work_dir / "metadata.json").write_text(
        json.dumps({"url": url, **info, "model": model_size}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ZIP
    zip_path = work_dir / "all_files.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in work_dir.rglob("*"):
            if f.is_file() and f.name not in ("all_files.zip", "cookies.txt"):
                zf.write(f, f.relative_to(work_dir))

    # ── 結果表示 ──────────────────────────────────────────────────────────────
    st.divider()
    st.success(f"✅ 処理完了！出力フォルダ: `{work_dir}`")

    tab1, tab2, tab3 = st.tabs(["📝 文字起こし", "📸 スナップショット", "📊 サマリ"])

    with tab1:
        total_chars = sum(len(s["text"]) for s in segments)
        st.subheader(f"全文テキスト（{total_chars:,} 文字）")
        st.text_area("", format_transcript(segments), height=420, label_visibility="collapsed")
        st.download_button(
            "📥 文字起こし Markdown をダウンロード",
            data=transcript_path.read_text(encoding="utf-8"),
            file_name=f"transcript_{session_id}.md",
            mime="text/markdown",
        )

    with tab2:
        if snapshot_list:
            cols = st.columns(3)
            for i, (ts, snap_path) in enumerate(snapshot_list):
                h, rem = divmod(ts, 3600)
                m, s = divmod(rem, 60)
                with cols[i % 3]:
                    st.image(str(snap_path), caption=f"{h:02d}:{m:02d}:{s:02d}", use_container_width=True)
        else:
            st.info("スナップショットはありません（設定をオンにして再実行してください）")

    with tab3:
        if summary_md:
            st.markdown(summary_md)
            st.download_button(
                "📥 サマリ Markdown をダウンロード",
                data=summary_md,
                file_name=f"summary_{session_id}.md",
                mime="text/markdown",
            )
        else:
            st.info("サマリが生成されていません（サイドバーで API Key を設定してください）")

    st.download_button(
        "📦 全ファイルを ZIP でダウンロード",
        data=zip_path.read_bytes(),
        file_name=f"vtt_{session_id}.zip",
        mime="application/zip",
    )
