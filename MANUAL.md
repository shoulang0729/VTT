# VTT 利用マニュアル

YouTube / Newspicks の動画を文字起こし・スナップショット記録し、プレゼン用サマリを生成するローカルアプリの導入・操作マニュアルです。

---

## 目次

1. [動作環境](#1-動作環境)
2. [セットアップ（Windows）](#2-セットアップwindows)
3. [セットアップ（Mac）](#3-セットアップmac)
4. [Anthropic API Key の取得](#4-anthropic-api-key-の取得)
5. [アプリの起動](#5-アプリの起動)
6. [基本的な使い方](#6-基本的な使い方)
7. [設定項目の説明](#7-設定項目の説明)
8. [Newspicks 有料コンテンツの使い方](#8-newspicks-有料コンテンツの使い方)
9. [出力ファイルの見方](#9-出力ファイルの見方)
10. [トラブルシューティング](#10-トラブルシューティング)

---

## 1. 動作環境

| 項目 | 要件 |
|------|------|
| OS | Windows 10/11、macOS 12 以降 |
| Python | 3.10 以上 |
| メモリ | 8GB 以上推奨（Whisper medium 使用時） |
| ディスク | 5GB 以上の空き（Whisperモデル + 作業領域） |
| ネットワーク | 動画DL・初回モデルDL・サマリ生成時に必要 |

> 文字起こし自体はローカル処理のため、モデルDL後はオフラインでも動作します（サマリ生成のみ Claude API を使用）。

---

## 2. セットアップ（Windows）

### 2-1. Python のインストール

すでに Python 3.10 以上が入っているか確認：

```powershell
python --version
```

入っていない場合は、PowerShell で：

```powershell
winget install Python.Python.3.12
```

または [python.org](https://www.python.org/downloads/) からインストーラーをダウンロード。
**インストール時に「Add Python to PATH」に必ずチェック**を入れてください。

### 2-2. ffmpeg のインストール

```powershell
winget install ffmpeg
```

インストール後、**新しいターミナルを開いて**確認：

```powershell
ffmpeg -version
```

バージョン情報が表示されればOK。

### 2-3. アプリ本体の配置

Git を使う場合：

```powershell
git clone https://github.com/shoulang0729/VTT.git
cd VTT
```

Git がない場合は、GitHub のリポジトリページから「Code → Download ZIP」でダウンロードして展開し、そのフォルダにターミナルで移動。

### 2-4. 依存ライブラリのインストール

仮想環境の利用を推奨します：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> `.venv\Scripts\activate` で「スクリプトの実行が無効」エラーが出る場合：
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> を実行してから再度試してください。

---

## 3. セットアップ（Mac）

### 3-1. Homebrew のインストール（未導入の場合）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3-2. Python と ffmpeg のインストール

```bash
brew install python@3.12 ffmpeg
```

確認：

```bash
python3 --version
ffmpeg -version
```

### 3-3. アプリ本体の配置

```bash
git clone https://github.com/shoulang0729/VTT.git
cd VTT
```

### 3-4. 依存ライブラリのインストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Anthropic API Key の取得

サマリ生成（プレゼン構成案の自動作成）に使用します。**文字起こしとスナップショットだけなら不要**です。

1. [console.anthropic.com](https://console.anthropic.com/) にアクセスしてアカウント作成
2. 左メニューの **API Keys** → **Create Key**
3. 表示されたキー（`sk-ant-...`）をコピー

### キーの設定方法（2通り）

**方法A: .env ファイルに保存（推奨・毎回入力不要）**

プロジェクトフォルダで：

```bash
# Windows (PowerShell)
copy .env.example .env

# Mac
cp .env.example .env
```

`.env` をテキストエディタで開いて編集：

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

**方法B: アプリ起動後にサイドバーで都度入力**

設定ファイルを作らず、画面のサイドバー「Anthropic API Key」欄に直接貼り付けてもOK。

> ⚠️ API Key は他人に共有しないでください。`.env` は `.gitignore` 済みなので Git にはコミットされません。

---

## 5. アプリの起動

プロジェクトフォルダで仮想環境を有効化してから起動します。

**Windows:**

```powershell
cd VTT
.venv\Scripts\activate
streamlit run app.py
```

**Mac:**

```bash
cd VTT
source .venv/bin/activate
streamlit run app.py
```

自動的にブラウザが開きます。開かない場合は `http://localhost:8501` にアクセス。

**終了するには** ターミナルで `Ctrl + C`。

---

## 6. 基本的な使い方

1. **URL を入力** — 画面中央の入力欄に YouTube または Newspicks の動画URLを貼り付け
2. **「▶ 処理開始」をクリック**
3. 以下のステップが順番に実行されます：

   | ステップ | 内容 | 所要時間の目安 |
   |---------|------|--------------|
   | 動画情報取得 | タイトル・長さの確認 | 数秒 |
   | 音声ダウンロード | 音声トラックのみDL | 動画長による（数十秒〜） |
   | 文字起こし | ローカルWhisperで処理 | **動画長の0.5〜2倍程度**（CPU・モデルサイズによる） |
   | スナップショット | 動画DL + 静止画抽出 | 数十秒〜数分 |
   | サマリ生成 | Claude API で生成 | 30秒〜1分 |

4. **結果を確認** — 処理完了後、3つのタブで結果を確認：
   - 📝 **文字起こし** — タイムスタンプ付き全文テキスト
   - 📸 **スナップショット** — 抽出された静止画の一覧
   - 📊 **サマリ** — エグゼクティブサマリ・スライド構成案・想定Q&A
5. **ダウンロード** — 各タブのダウンロードボタン、または最下部の「📦 全ファイルを ZIP でダウンロード」

> 💡 **初回実行時の注意**: 文字起こしの初回はWhisperモデルのダウンロードが走ります（medium で約1.5GB、回線によっては10分以上）。2回目以降は不要です。

---

## 7. 設定項目の説明

すべてサイドバー（画面左）にあります。

### Whisperモデル

| モデル | DLサイズ | 速度 | 精度 | おすすめの場面 |
|--------|---------|------|------|--------------|
| tiny | 75MB | 最速 | 低 | 動作確認・お試し |
| base | 145MB | 速い | 普通 | 短い動画をサッと |
| small | 465MB | 普通 | 良い | 速度と精度のバランス |
| **medium** | **1.5GB** | 遅い | **高い** | **日本語動画の標準（推奨）** |
| large-v3 | 3GB | 最遅 | 最高 | 精度最優先・専門用語が多い |

### 言語

- **日本語** — 日本語動画はこれを選択（精度が安定します）
- **English** — 英語動画用
- **自動検出** — 言語不明な場合。冒頭の音声から自動判定

### スナップショット取得 / 間隔

- オン/オフ切り替え可能。オフにすると動画本体のDLをスキップするので高速
- 間隔は 15〜300 秒。スライド切り替えが多いプレゼン動画は短め（30秒）、トーク中心なら長め（120秒〜）が目安

### Anthropic API Key

- サマリ生成に使用。`.env` に設定済みなら自動入力されます
- 空のままでも文字起こし・スナップショットは動作します（サマリのみスキップ）

### Cookie ファイル

- Newspicks 有料コンテンツ等のログインが必要な動画用（→ [次章](#8-newspicks-有料コンテンツの使い方)）

---

## 8. Newspicks 有料コンテンツの使い方

有料会員限定の動画は、ブラウザのログイン情報（Cookie）をアプリに渡す必要があります。

### 手順（Chrome の場合）

1. Chrome 拡張 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) をインストール
2. Chrome で [newspicks.com](https://newspicks.com/) にログインした状態で開く
3. 拡張アイコンをクリック → **Export** で `newspicks.com_cookies.txt` をダウンロード
4. VTT のサイドバー「Cookie ファイル」にこのファイルをアップロード
5. 通常どおり URL を入力して処理開始

> ⚠️ Cookie ファイルはあなたのログイン情報そのものです。**他人と共有しない・共用PCに残さない**よう注意してください。アプリは出力 ZIP に Cookie を含めません。
> Cookie の有効期限が切れるとDLに失敗します。その場合は再エクスポートしてください。

---

## 9. 出力ファイルの見方

処理ごとに `output/日時/` フォルダが作られます：

```
output/
└── 20260612_143000/
    ├── transcript.md     # タイムスタンプ付き全文テキスト
    ├── summary.md        # サマリ＋スライド構成案（API Key設定時のみ）
    ├── metadata.json     # 動画タイトル・URL等のメタ情報
    ├── audio/            # ダウンロードした音声（中間ファイル）
    ├── video/            # ダウンロードした動画（中間ファイル）
    ├── snapshots/        # 静止画（snapshot_00_01_00.jpg = 1分時点）
    └── all_files.zip     # 上記一式のZIP
```

### プレゼン資料への活用フロー

1. `summary.md` の「プレゼンテーション構成案」をベースにスライドの骨子を作成
2. `snapshots/` から該当シーンの画像を選んでスライドに挿入
3. `transcript.md` のタイムスタンプで該当箇所の正確な発言を確認
4. 「想定Q&A」セクションで質疑応答の準備

> 💡 `summary.md` / `transcript.md` は Markdown なので、Notion・Obsidian にそのまま貼り付けられます。

### ディスク容量の管理

`output/` フォルダは自動削除されません。中間ファイル（audio/ video/）は容量が大きいので、不要になったセッションフォルダは手動で削除してください。

---

## 10. トラブルシューティング

### `streamlit: command not found` / `streamlit が認識されません`

仮想環境が有効化されていません。起動前に必ず：

```
Windows: .venv\Scripts\activate
Mac:     source .venv/bin/activate
```

### `ffmpeg not found` 系のエラー

- ffmpeg がインストールされていないか、PATH に通っていません
- インストール後は**ターミナルを開き直して**から再実行してください
- 確認: `ffmpeg -version` が通るか

### 動画情報取得・ダウンロードに失敗する

- **URL を確認** — 動画ページのURLか（チャンネルページや検索結果ページは不可）
- **yt-dlp を最新化** — YouTube 側の仕様変更で古い yt-dlp が動かなくなることがあります：
  ```bash
  pip install -U yt-dlp
  ```
- **Newspicks で失敗** — Cookie ファイルが必要、または期限切れの可能性（→ [8章](#8-newspicks-有料コンテンツの使い方)）
- **メンバー限定・年齢制限付き YouTube** — Newspicks と同様に Cookie ファイルで対応可能

### 文字起こしが非常に遅い

- モデルを `small` や `base` に下げる（サイドバーで変更）
- 他の重いアプリを閉じてメモリを確保
- 目安: medium モデルで CPU 処理の場合、60分動画に30分〜2時間程度かかることがあります

### 文字起こしの精度が低い

- モデルを `medium` 以上に上げる
- 言語を「自動検出」ではなく明示的に「日本語」を選択
- BGMが大きい動画・複数人が同時に話す動画は精度が落ちやすいです

### サマリ生成に失敗する

- API Key が正しいか確認（`sk-ant-` で始まる）
- [console.anthropic.com](https://console.anthropic.com/) でクレジット残高を確認
- 非常に長い動画（3時間超など）は文字起こしがモデルの入力上限を超える場合があります

### 初回の文字起こしで長時間止まっているように見える

Whisperモデルのダウンロード中の可能性が高いです（medium で約1.5GB）。回線速度によっては10分以上かかります。2回目以降は発生しません。

### ポート 8501 が使用中と言われる

別の Streamlit アプリが起動中です。既存のものを終了するか、別ポートで起動：

```bash
streamlit run app.py --server.port 8502
```

---

## 補足: アップデート方法

```bash
cd VTT
git pull
pip install -U -r requirements.txt
pip install -U yt-dlp   # yt-dlp は頻繁に更新されるため個別に最新化推奨
```
