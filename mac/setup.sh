#!/usr/bin/env bash
# VTT Live (Mac) セットアップ確認スクリプト
# 必要なツールの有無を確認し、足りないものはインストール方法を案内する。
set -uo pipefail

echo "== VTT Live セットアップ確認 =="

need_install=0

check() {  # name  install_hint
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ✅ $1 : $(command -v "$1")"
  else
    echo "  ❌ $1 が見つかりません → $2"
    need_install=1
  fi
}

check ffmpeg "brew install ffmpeg"
check buzz   "brew install --cask buzz  （または: pipx install buzz-captions）"

echo
echo "-- BlackHole（仮想オーディオ）--"
if system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole; then
  echo "  ✅ BlackHole がオーディオデバイスとして見つかりました"
else
  echo "  ❌ BlackHole が見つかりません → brew install blackhole-2ch"
  need_install=1
fi

echo
echo "-- ffmpeg から見える音声入力デバイス --"
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 \
  | sed -n '/AVFoundation audio devices/,$p' \
  | grep -E "\[[0-9]+\]" || echo "  （取得できませんでした）"

cat <<'EOS'

-- 次の手動設定（初回のみ）--
  1. 「Audio MIDI設定」を開く（Spotlightで "Audio MIDI" 検索）
  2. 左下「＋」→「複数出力装置を作成」
  3. 「内蔵スピーカー（やヘッドフォン）」と「BlackHole 2ch」の両方にチェック
  4. システム設定 > サウンド > 出力 を、その複数出力装置に変更
     → 自分の耳でも聞こえつつ、BlackHole にも音が流れる状態になる

-- 実行例 --
  export OPENAI_API_KEY=sk-...            # 精度優先（クラウドAPI）の場合
  python3 mac/vtt_live.py                 # 既定: openaiapi / 日本語 / 20秒チャンク
  python3 mac/vtt_live.py --engine fasterwhisper --model-size medium   # 完全ローカル
EOS

if [ "$need_install" -eq 0 ]; then
  echo
  echo "== 必要ツールは揃っています =="
fi
