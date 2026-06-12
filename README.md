# VTT — 動画文字起こし & プレゼン資料作成ツール

YouTube / Newspicks の動画を文字起こし・スナップショット記録して、プレゼン用サマリを生成するローカルWebアプリです。

> 📖 別環境への導入・詳しい操作手順は **[MANUAL.md](MANUAL.md)** を参照してください。

## 機能

- **文字起こし** — ローカル Whisper（faster-whisper）で音声をテキスト化（日本語・英語・自動検出）
- **スナップショット** — 指定間隔で動画の静止画を抽出
- **サマリ生成** — Claude API でエグゼクティブサマリ・スライド構成案・想定Q&Aを生成
- **出力** — 全文テキスト（Markdown）+ サマリ（Markdown）+ スナップショット（JPG）を ZIP でダウンロード

## セットアップ

### 必要なもの

- Python 3.10 以上
- [ffmpeg](https://ffmpeg.org/download.html)（パスに通しておく）
- Anthropic API Key（サマリ生成を使う場合）

### インストール

```bash
# 依存ライブラリ
pip install -r requirements.txt

# 環境変数（任意）
cp .env.example .env
# .env を開いて ANTHROPIC_API_KEY を設定
```

### 起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が開きます。

## 使い方

1. サイドバーで Whisper モデルサイズ・言語・API Key を設定
2. URL 欄に YouTube または Newspicks の URL を入力
3. **「▶ 処理開始」** をクリック
4. 処理が完了したらタブで結果を確認し、ダウンロード

### Newspicks 有料コンテンツの場合

ブラウザの Cookie を Netscape 形式でエクスポートして、サイドバーの「Cookie ファイル」にアップロードしてください。  
（Chrome 拡張: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 等）

## 出力ファイル構成

```
output/
└── 20240101_120000/
    ├── transcript.md       全文テキスト（タイムスタンプ付き）
    ├── summary.md          エグゼクティブサマリ＋スライド構成案
    ├── metadata.json       動画メタデータ
    ├── snapshots/          静止画（snapshot_00_01_00.jpg など）
    └── all_files.zip       上記一式
```

## Whisper モデルの目安

| モデル | サイズ | 速度 | 精度 |
|--------|--------|------|------|
| tiny   | 75MB   | 最速 | 低   |
| base   | 145MB  | 速い | 普通 |
| small  | 465MB  | 普通 | 良い |
| medium | 1.5GB  | 遅い | 高い |（推奨）
| large-v3 | 3GB  | 最遅 | 最高 |

初回起動時にモデルが自動ダウンロードされます（`~/.cache/huggingface/hub`）。
