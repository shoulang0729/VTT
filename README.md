# VTT

ブラウザで再生できる動画やスピーチを全文文字起こし。

## mac/ — Mac向け簡易ツール（Buzzを裏で呼び出す）

同一Mac内で鳴っているシステム音声（ブラウザ/アプリの動画など）を
[BlackHole](https://github.com/ExistentialAudio/BlackHole) 経由で連続録音し、短いチャンクごとに
[Buzz](https://github.com/chidiwilliams/buzz) の CLI を裏で呼び出して、ほぼリアルタイムに
文字起こしする `mac/vtt_live.py`。

精度優先で OpenAI Whisper API（クラウド）を既定エンジンにしているが、完全ローカル
（faster-whisper / whisper.cpp）にも切り替え可能。

### できること / 制約

- ✅ ブラウザ・アプリ問わず、Macで鳴っている音をまとめて文字起こし
- ✅ 文字起こし中も別の（**無音の**）作業は可能。自分の耳でも音を聞ける
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
python3 mac/vtt_live.py

# 完全ローカル（オフライン・無料）で動かす場合
python3 mac/vtt_live.py --engine fasterwhisper --model-size medium

# 主なオプション
#   --language ja|en|auto   言語（既定 ja、auto で自動判定）
#   --chunk-sec 20          1チャンクの秒数（短いほど低遅延）
#   --out transcript.txt    保存先ファイル
```

実行すると字幕が逐次表示され、同時に `transcript_YYYYmmdd_HHMMSS.txt` へ追記される。
停止は `Ctrl+C`（残りのチャンクを処理してから終了）。
