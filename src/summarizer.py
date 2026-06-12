import anthropic
from pathlib import Path

_SYSTEM = "あなたは動画コンテンツを分析してプレゼンテーション資料を作成するアシスタントです。簡潔で明確な日本語で回答してください。"

_PROMPT = """\
以下の動画の文字起こしを分析して、プレゼンテーション用の資料を作成してください。

## 動画情報
- タイトル: {title}
- 時間: {duration_str}
- 投稿者: {uploader}

## 文字起こし
{transcript}

---

以下の構成でMarkdownドキュメントを作成してください：

# {title}

## エグゼクティブサマリ
（3〜5行で動画の要点を端的に記述）

## 主要なポイント
（箇条書き5〜8個で重要な論点を列挙）

## プレゼンテーション構成案

### スライド1: [タイトル・全体概要]
- ...

### スライド2: [タイトル]
- ...

（以降、合計6〜8枚のスライド構成。各スライドにタイトルと3〜5個の箇条書き）

## 詳細メモ
（プレゼンで触れるべき補足情報や具体的なデータ・事例）

## 想定Q&A
（このプレゼンで出そうな質問と回答を3〜5個）
"""


def format_transcript(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        ts = int(seg["start"])
        h, rem = divmod(ts, 3600)
        m, s = divmod(rem, 60)
        lines.append(f"[{h:02d}:{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}時間{m}分{s}秒" if h > 0 else f"{m}分{s}秒"


def generate_summary(
    title: str,
    uploader: str,
    duration: float,
    segments: list[dict],
    api_key: str,
) -> str:
    client = anthropic.Anthropic(api_key=api_key)

    prompt = _PROMPT.format(
        title=title,
        duration_str=_format_duration(duration),
        uploader=uploader,
        transcript=format_transcript(segments),
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
