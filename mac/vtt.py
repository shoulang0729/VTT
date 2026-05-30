#!/usr/bin/env python3
"""VTT (Mac) — 録音してから一括文字起こし

同一Mac内で鳴っているシステム音声（ブラウザ/アプリの動画など）を BlackHole 経由で
1ファイルに録音し、停止後にまとめて Buzz の CLI (`buzz add`) で文字起こしする簡易ツール。
「聞きながら」ではなく「全部再生し終わったら文字が残っている」用途向け。

使い方:
  python3 mac/vtt.py                 # 録音開始 → 再生 → Ctrl+C で停止＆文字起こし
  python3 mac/vtt.py --url URL       # YouTube等のURLから音声を取得して文字起こし（録音不要）
  python3 mac/vtt.py --file foo.mp4  # 既存の音声/動画ファイルをそのまま文字起こし

前提: ffmpeg / buzz / blackhole-2ch をインストールし、複数出力装置を設定済みであること
      （詳細は `bash mac/setup.sh`）。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def die(msg: str) -> None:
    print(f"[VTT] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def find_blackhole_index() -> tuple[str, str]:
    proc = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True, text=True,
    )
    in_audio = False
    for line in proc.stderr.splitlines():
        if "AVFoundation video devices" in line:
            in_audio = False
            continue
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if in_audio:
            m = re.search(r"\[(\d+)\]\s+(.*)$", line)
            if m and "blackhole" in m.group(2).lower():
                return m.group(1), m.group(2).strip()
    die("BlackHole の入力デバイスが見つかりません。`bash mac/setup.sh` で設定を確認してください。\n"
        + proc.stderr)
    raise SystemExit


def record_system_audio(device_index: str) -> Path:
    """Ctrl+C まで BlackHole の音声を1ファイルに録音し、そのパスを返す。"""
    wav = Path(f"recording_{datetime.now():%Y%m%d_%H%M%S}.wav")
    cmd = [
        "ffmpeg", "-loglevel", "error", "-y",
        "-f", "avfoundation", "-i", f":{device_index}",
        "-ac", "1", "-ar", "16000",
        str(wav),
    ]
    print(f"[VTT] 録音中… 対象を再生してください。停止は Ctrl+C。→ {wav}")
    ff = subprocess.Popen(cmd)

    # Ctrl+C は ffmpeg に渡して正常終了させ、WAVヘッダを確定させる
    signal.signal(signal.SIGINT, lambda *_: ff.send_signal(signal.SIGINT))
    ff.wait()
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    if not wav.exists() or wav.stat().st_size < 1024:
        die("録音ファイルが空です。複数出力装置/サウンド出力の設定を確認してください。")
    print(f"[VTT] 録音停止。({wav.stat().st_size/1024/1024:.1f} MB)")
    return wav


def download_url_audio(url: str, cookies_browser: str | None) -> Path:
    """yt-dlp で URL から音声だけを取得し、そのファイルパスを返す。

    yt-dlp は YouTube / Voicy / NewsPicks など1800以上のサイトに対応。対応サイトなら
    サイトを問わずこの1経路で処理できる（=「URLで判断」）。取得できない場合は録音モードを案内。
    """
    if shutil.which("yt-dlp") is None:
        die("`yt-dlp` が見つかりません。`brew install yt-dlp` を実行してください。")
    base = f"yt_{datetime.now():%Y%m%d_%H%M%S}"
    cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", base + ".%(ext)s"]
    if cookies_browser:
        # 有料・ログイン必須コンテンツ（Voicyプレミアム/NewsPicks有料 等）をブラウザのログインで取得
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd.append(url)
    print(f"[VTT] 音声をダウンロード中… {url}")
    if subprocess.run(cmd).returncode != 0:
        die("このURLからは音声を直接取得できませんでした（未対応サイト/ログイン必須/DRM など）。\n"
            "  対処1: ログインが必要なら  --cookies-from-browser chrome  を付けて再実行\n"
            "  対処2: それでも無理なら、ブラウザで再生しながら録音モードで取り込む:\n"
            "         python3 mac/vtt.py        （対象の音だけ鳴らし、通知はミュート）")
    media = Path(base + ".mp3")
    if not media.exists():
        die("ダウンロードは成功しましたが音声ファイルが見つかりません。")
    return media


def transcribe(media: Path, args: argparse.Namespace) -> None:
    cmd = ["buzz", "add", "--task", "transcribe",
           "--model-type", args.engine, "--txt", "--srt", "--hide-gui"]
    if args.language and args.language != "auto":
        cmd += ["--language", args.language]
    if args.engine in ("whisper", "whispercpp", "fasterwhisper"):
        cmd += ["--model-size", args.model_size]
    if args.engine == "openaiapi":
        token = args.openai_token or os.environ.get("OPENAI_API_KEY")
        if token:
            cmd += ["--openai-token", token]
    cmd.append(str(media))

    print(f"[VTT] 文字起こし中… (engine={args.engine}, language={args.language})")
    if subprocess.run(cmd).returncode != 0:
        die("buzz による文字起こしに失敗しました。")

    txt = media.with_suffix(".txt")
    if txt.exists():
        body = txt.read_text(errors="ignore").strip()
        print(f"\n[VTT] 完了 → {txt}  /  字幕: {media.with_suffix('.srt')}\n")
        print(body[:1000] + ("\n…(以下略)" if len(body) > 1000 else ""))
    else:
        print("[VTT] 完了しましたが .txt が見つかりませんでした。出力設定を確認してください。")


def main() -> None:
    p = argparse.ArgumentParser(description="Macのシステム音声を録音してBuzzで一括文字起こし")
    p.add_argument("--file", default=None, help="録音せず、既存の音声/動画ファイルを文字起こし")
    p.add_argument("--url", default=None,
                   help="URLから音声を取得して文字起こし（YouTube/Voicy/NewsPicks等・録音不要）")
    p.add_argument("--cookies-from-browser", default=None, metavar="BROWSER",
                   help="ログイン必須/有料コンテンツ用。例: chrome / safari / firefox")
    p.add_argument("--engine", default="openaiapi",
                   choices=["openaiapi", "fasterwhisper", "whispercpp", "whisper", "huggingface"],
                   help="文字起こしエンジン (既定: openaiapi=高精度クラウド)")
    p.add_argument("--model-size", default="medium", help="ローカルエンジン時のモデルサイズ")
    p.add_argument("--language", default="ja", help="言語コード。'auto'で自動判定 (既定: ja)")
    p.add_argument("--openai-token", default=None, help="OpenAI APIキー (既定: 環境変数 OPENAI_API_KEY)")
    p.add_argument("--device-index", default=None, help="BlackHole の入力インデックスを手動指定")
    args = p.parse_args()

    for tool in ("ffmpeg", "buzz"):
        if shutil.which(tool) is None:
            die(f"`{tool}` が見つかりません。`bash mac/setup.sh` を実行してください。")

    if args.url:
        media = download_url_audio(args.url, args.cookies_from_browser)
    elif args.file:
        media = Path(args.file)
        if not media.exists():
            die(f"ファイルが見つかりません: {media}")
    else:
        idx = args.device_index or find_blackhole_index()[0]
        media = record_system_audio(idx)

    transcribe(media, args)


if __name__ == "__main__":
    main()
