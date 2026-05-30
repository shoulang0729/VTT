# VTT

ブラウザで再生できる動画やスピーチを全文文字起こし。

## mac/ — Mac向け簡易ツール（録音 → 一括文字起こし）

同一Mac内で鳴っているシステム音声（ブラウザ/アプリの動画など）を
[BlackHole](https://github.com/ExistentialAudio/BlackHole) 経由で1ファイルに録音し、停止後に
[Buzz](https://github.com/chidiwilliams/buzz) の CLI を裏で1回呼び出してまとめて文字起こしする
`mac/vtt.py`。「聞きながら」ではなく「全部再生し終わったら文字が残っている」用途向け。

精度優先で OpenAI Whisper API（クラウド）を既定エンジンにしているが、完全ローカル
（faster-whisper / whisper.cpp）にも切り替え可能。

### できること / 制約

- ✅ ブラウザ・アプリ問わず、Macで鳴っている音をまとめて文字起こし
- ✅ 録音中は別の（**無音の**）作業をしてOK。自分の耳でも音を聞ける
- ✅ 録音せず既存の音声/動画ファイルを直接文字起こしも可（`--file`）
- ⚠️ システム音声の「ミックス全体」を拾うため、対象の動画以外の音（通知音・別の動画・
  音楽・通話）も一緒に文字起こしされる → **対象の音だけ鳴らし、通知はミュート推奨**
- ⚠️ 「動画を再生せずデータから直接読む」ことは汎用的には不可（DRM/ストリーム暗号化のため）。
  本ツールは再生中の音声出力を拾う方式

### 前提（インストール）

```bash
brew install ffmpeg
brew install --cask buzz        # または: pipx install buzz-captions
brew install blackhole-2ch
```

その後、初回のみ「Audio MIDI設定」で**複数出力装置**を作成し、内蔵スピーカー＋BlackHole を
まとめてシステム出力に設定する（詳細は `bash mac/setup.sh` が案内）。

### 使い方

```bash
# 環境確認（不足ツールや設定手順を表示）
bash mac/setup.sh

# 精度優先（クラウドAPI）。APIキーを環境変数で渡す
export OPENAI_API_KEY=sk-...
python3 mac/vtt.py              # 録音開始 → 対象を再生 → Ctrl+C で停止＆文字起こし

# 完全ローカル（オフライン・無料）で動かす場合
python3 mac/vtt.py --engine fasterwhisper --model-size medium

# 録音せず既存ファイルを文字起こし
python3 mac/vtt.py --file movie.mp4

# 主なオプション
#   --language ja|en|auto   言語（既定 ja、auto で自動判定）
#   --file PATH             既存の音声/動画ファイルを文字起こし
```

`Ctrl+C` で録音を停止すると、その場でまとめて文字起こしし、入力と同じ名前の
`recording_*.txt`（本文）と `recording_*.srt`（字幕）を書き出す。
