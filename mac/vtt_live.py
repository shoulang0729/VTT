#!/usr/bin/env python3
"""VTT Live (Mac)

同一Mac内で鳴っているシステム音声（ブラウザ/アプリの動画など）を BlackHole 経由で
連続録音し、短いチャンクごとに Buzz の CLI (`buzz add`) を裏で呼び出して文字起こしする
簡易ツール。結果は標準出力に流しつつ、テキストファイルへ追記する。

前提:
  - ffmpeg がインストール済み           (brew install ffmpeg)
  - Buzz がインストール済みで `buzz` がPATHにある (brew install --cask buzz / pipx install buzz-captions)
  - BlackHole がインストール済み         (brew install blackhole-2ch)
  - 「複数出力装置」で 内蔵スピーカー + BlackHole を作り、システム出力をそれに設定
    （自分の耳でも聞きつつ BlackHole にも音を流すため）

仕組み:
  ffmpeg が BlackHole から N 秒ごとのWAVセグメントを連続生成 → 完成したセグメントを
  順番に `buzz add ... --txt` で文字起こし → 生成された .txt を読んで追記/表示。
  ffmpeg は録音を止めないので、文字起こし中に音声が欠落しない（遅延はするが取りこぼさない）。

注意:
  システム音声の「ミックス全体」を拾うため、対象の動画以外の音（通知音・別の動画・音楽・
  通話など）も一緒に文字起こしされてしまう。対象の音だけを鳴らし、通知はミュート推奨。
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def die(msg: str) -> None:
    print(f"[VTT] エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def check_prereqs() -> None:
    for tool in ("ffmpeg", "buzz"):
        if shutil.which(tool) is None:
            die(
                f"`{tool}` が見つかりません。README の前提（インストール手順）を確認してください。"
            )


def find_blackhole_index() -> tuple[str, str]:
    """ffmpeg の avfoundation デバイス一覧から BlackHole の入力インデックスを探す。"""
    proc = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    in_audio = False
    for line in proc.stderr.splitlines():
        if "AVFoundation video devices" in line:
            in_audio = False
            continue
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if not in_audio:
            continue
        m = re.search(r"\[(\d+)\]\s+(.*)$", line)
        if m and "blackhole" in m.group(2).lower():
            return m.group(1), m.group(2).strip()
    die(
        "BlackHole の入力デバイスが見つかりません。`brew install blackhole-2ch` 後、"
        "Audio MIDI設定で複数出力装置を作り、システム出力をそれに設定してください。\n"
        "現在の入力デバイス一覧:\n" + proc.stderr
    )
    raise SystemExit  # for type-checkers


def start_ffmpeg(device_index: str, seg_dir: Path, chunk_sec: int) -> subprocess.Popen:
    pattern = str(seg_dir / "seg_%05d.wav")
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-f", "avfoundation",
        "-i", f":{device_index}",   # ":N" = 音声のみ（映像なし）
        "-ac", "1",
        "-ar", "16000",
        "-f", "segment",
        "-segment_time", str(chunk_sec),
        "-reset_timestamps", "1",
        pattern,
    ]
    return subprocess.Popen(cmd)


def build_buzz_cmd(wav: Path, args: argparse.Namespace) -> list[str]:
    cmd = [
        "buzz", "add",
        "--task", "transcribe",
        "--model-type", args.engine,
        "--txt",
        "--hide-gui",
    ]
    if args.language and args.language != "auto":
        cmd += ["--language", args.language]
    if args.engine in ("whisper", "whispercpp", "fasterwhisper"):
        cmd += ["--model-size", args.model_size]
    if args.engine == "openaiapi":
        token = args.openai_token or os.environ.get("OPENAI_API_KEY")
        if token:
            cmd += ["--openai-token", token]
    cmd.append(str(wav))
    return cmd


def transcribe_segment(wav: Path, args: argparse.Namespace) -> str:
    """1セグメントを buzz に渡し、生成された .txt の中身を返す。"""
    before = set(wav.parent.glob("*.txt"))
    proc = subprocess.run(build_buzz_cmd(wav, args), capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[VTT] buzz が失敗 (code {proc.returncode}): {proc.stderr.strip()}",
              file=sys.stderr)
        return ""
    new_txts = list(set(wav.parent.glob("*.txt")) - before)
    # 同じベース名の .txt を優先、なければ新規に出来たものを使う
    same = [p for p in new_txts if p.stem == wav.stem]
    cand = same or new_txts
    if not cand:
        return ""
    text = cand[0].read_text(errors="ignore").strip()
    for p in cand:
        p.unlink(missing_ok=True)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Macのシステム音声(BlackHole)を Buzz で逐次文字起こしする簡易ツール"
    )
    parser.add_argument("--engine", default="openaiapi",
                        choices=["openaiapi", "fasterwhisper", "whispercpp", "whisper", "huggingface"],
                        help="文字起こしエンジン (既定: openaiapi=高精度クラウド)")
    parser.add_argument("--model-size", default="small",
                        help="ローカルエンジン使用時のモデルサイズ (tiny/base/small/medium/large)")
    parser.add_argument("--language", default="ja",
                        help="言語コード。'auto' で自動判定 (既定: ja)")
    parser.add_argument("--chunk-sec", type=int, default=20,
                        help="1チャンクの秒数。短いほど低遅延だがbuzz起動の割合が増える (既定: 20)")
    parser.add_argument("--openai-token", default=None,
                        help="OpenAI APIキー。未指定なら環境変数 OPENAI_API_KEY または Buzz保存済みトークン")
    parser.add_argument("--device-index", default=None,
                        help="BlackHole の入力インデックスを手動指定する場合")
    parser.add_argument("--out", default=None,
                        help="文字起こしの保存先 (既定: transcript_YYYYmmdd_HHMMSS.txt)")
    args = parser.parse_args()

    check_prereqs()

    if args.device_index:
        dev_idx, dev_name = args.device_index, f"(index {args.device_index})"
    else:
        dev_idx, dev_name = find_blackhole_index()

    out_path = Path(args.out) if args.out else Path(
        f"transcript_{datetime.now():%Y%m%d_%H%M%S}.txt")

    seg_dir = Path(".vtt_segments")
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    print(f"[VTT] 入力デバイス : [{dev_idx}] {dev_name}")
    print(f"[VTT] エンジン     : {args.engine} (language={args.language})")
    print(f"[VTT] チャンク     : {args.chunk_sec}s")
    print(f"[VTT] 保存先       : {out_path}")
    print("[VTT] 録音開始。停止は Ctrl+C。対象の音だけを鳴らし通知はミュート推奨。\n")

    ff = start_ffmpeg(dev_idx, seg_dir, args.chunk_sec)

    stopping = {"flag": False}

    def handle_sigint(signum, frame):
        if not stopping["flag"]:
            print("\n[VTT] 停止中… 残りのチャンクを処理します。", file=sys.stderr)
        stopping["flag"] = True

    signal.signal(signal.SIGINT, handle_sigint)

    processed = 0
    try:
        while True:
            segs = sorted(seg_dir.glob("seg_*.wav"))
            # 末尾のセグメントは録音中の可能性があるので、停止時以外は除外
            ready = segs if stopping["flag"] else segs[:-1]
            for wav in ready[processed:]:
                text = transcribe_segment(wav, args)
                wav.unlink(missing_ok=True)
                processed += 1
                if text:
                    stamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{stamp}] {text}")
                    with out_path.open("a", encoding="utf-8") as f:
                        f.write(text + "\n")
            if stopping["flag"] and processed >= len(segs):
                break
            if ff.poll() is not None and not stopping["flag"]:
                print("[VTT] ffmpeg が終了しました。", file=sys.stderr)
                stopping["flag"] = True
            time.sleep(0.5)
    finally:
        if ff.poll() is None:
            ff.terminate()
            try:
                ff.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ff.kill()
        shutil.rmtree(seg_dir, ignore_errors=True)
        print(f"\n[VTT] 完了。文字起こしは {out_path} に保存しました。")


if __name__ == "__main__":
    main()
