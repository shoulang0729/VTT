#!/usr/bin/env python3
"""VTT slides (Mac) — 動画からスライドを抽出してOCR（クラウドビジョンAI）

動画（URL or ローカルファイル）から「画面が切り替わった瞬間」のフレームを自動抽出し、
各スライド画像をクラウドのビジョンAI（OpenAI GPT-4o）に渡して、書かれている文字・図表の
要点をテキスト化する。要約はしない（スクショ＋OCRテキストまで）。

出力:
  slides_YYYYmmdd_HHMMSS/
    ├─ slide_0001.jpg, slide_0002.jpg, ...   抽出したスライド画像
    └─ slides.md                              各スライドのタイムスタンプ＋書き起こし

使い方:
  export OPENAI_API_KEY=sk-...
  python3 mac/slides.py --url "https://youtu.be/..."        # URLから
  python3 mac/slides.py --file talk.mp4                      # ローカル動画から
  python3 mac/slides.py --url URL --cookies-from-browser chrome   # ログイン必須コンテンツ

前提: ffmpeg（必須）, yt-dlp（--url時）, 環境変数 OPENAI_API_KEY
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OCR_PROMPT = (
    "この画像はプレゼン/講義動画のスライドです。スライドに書かれているテキストを"
    "そのまま（原文の言語のまま）漏れなく書き出し、図表があればその要点も箇条書きで"
    "補足してください。あなたの感想・推測・要約は不要です。文字が無い場合は「（文字なし）」"
    "とだけ返してください。"
)


def die(msg: str) -> None:
    print(f"[slides] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def download_video(url: str, cookies_browser: str | None) -> Path:
    if shutil.which("yt-dlp") is None:
        die("`yt-dlp` が見つかりません。`brew install yt-dlp` を実行してください。")
    base = f"video_{datetime.now():%Y%m%d_%H%M%S}"
    cmd = ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
           "-o", base + ".%(ext)s"]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd.append(url)
    print(f"[slides] 動画をダウンロード中… {url}")
    if subprocess.run(cmd).returncode != 0:
        die("動画を取得できませんでした（未対応サイト/ログイン必須/DRM など）。\n"
            "  ログインが必要なら --cookies-from-browser chrome を付けて再実行してください。")
    files = sorted(Path(".").glob(base + ".*"))
    if not files:
        die("ダウンロードした動画ファイルが見つかりません。")
    return files[0]


def extract_slides(video: Path, out_dir: Path, scene: float, every: int | None) -> list[float]:
    """シーン変化（既定）または一定間隔でフレームを抽出。各フレームのタイムスタンプ(秒)を返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = out_dir / "_meta.txt"
    if every:
        vf = f"fps=1/{every},metadata=print:file={meta}"
    else:
        vf = f"select='gt(scene,{scene})',metadata=print:file={meta}"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
           "-vf", vf, "-vsync", "vfr", "-q:v", "3",
           str(out_dir / "slide_%04d.jpg")]
    if subprocess.run(cmd).returncode != 0:
        die("フレーム抽出に失敗しました。")
    times: list[float] = []
    if meta.exists():
        for line in meta.read_text(errors="ignore").splitlines():
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                times.append(float(m.group(1)))
        meta.unlink(missing_ok=True)
    return times


def vision_ocr(image: Path, api_key: str, model: str) -> str:
    b64 = base64.b64encode(image.read_bytes()).decode()
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 1500,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        return f"（OCR失敗: HTTP {e.code} {body[:200]}）"
    except Exception as e:  # noqa: BLE001
        return f"（OCR失敗: {e}）"


def main() -> None:
    p = argparse.ArgumentParser(
        description="動画からスライドを抽出してビジョンAIでOCRする")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="動画URL（YouTube/Voicy/NewsPicks等）")
    src.add_argument("--file", help="ローカル動画ファイル")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="ログイン必須/有料コンテンツ用 (chrome/safari/firefox)")
    p.add_argument("--scene-threshold", type=float, default=0.3,
                   help="シーン変化の感度。小さいほど多く抽出 (既定 0.3)")
    p.add_argument("--every", type=int, default=None,
                   help="シーン検出でなくN秒ごとに抽出する場合の秒数")
    p.add_argument("--model", default="gpt-4o",
                   help="ビジョンモデル (既定 gpt-4o。安価重視なら gpt-4o-mini)")
    p.add_argument("--out", default=None, help="出力ディレクトリ")
    args = p.parse_args()

    if shutil.which("ffmpeg") is None:
        die("`ffmpeg` が見つかりません。`brew install ffmpeg` を実行してください。")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        die("環境変数 OPENAI_API_KEY が未設定です。`export OPENAI_API_KEY=sk-...` を実行してください。")

    if args.url:
        video = download_video(args.url, args.cookies_from_browser)
    else:
        video = Path(args.file)
        if not video.exists():
            die(f"ファイルが見つかりません: {video}")

    out_dir = Path(args.out) if args.out else Path(
        f"slides_{datetime.now():%Y%m%d_%H%M%S}")

    print("[slides] スライドを抽出中…")
    times = extract_slides(video, out_dir, args.scene_threshold, args.every)
    images = sorted(out_dir.glob("slide_*.jpg"))
    if not images:
        die("スライドを抽出できませんでした。--scene-threshold を下げる(例 0.2)か "
            "--every 30 で一定間隔抽出を試してください。")
    print(f"[slides] {len(images)} 枚を抽出。OCR中… (model={args.model})")

    md = out_dir / "slides.md"
    with md.open("w", encoding="utf-8") as f:
        f.write(f"# スライド書き起こし: {video.name}\n\n")
        for i, img in enumerate(images):
            ts = fmt_ts(times[i]) if i < len(times) else "??:??:??"
            text = vision_ocr(img, api_key, args.model)
            print(f"  [{ts}] {img.name} ✓")
            f.write(f"## [{ts}] {img.name}\n\n{text}\n\n")

    print(f"\n[slides] 完了 → {md}（画像は {out_dir}/ 内）")


if __name__ == "__main__":
    main()
