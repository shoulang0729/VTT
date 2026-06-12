from faster_whisper import WhisperModel
from pathlib import Path
from typing import Optional, Callable


def transcribe(
    audio_path: Path,
    model_size: str = "medium",
    language: Optional[str] = "ja",
    progress_callback: Optional[Callable[[float, float], None]] = None,
) -> list[dict]:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments_gen, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    segments = []
    for segment in segments_gen:
        segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
        if progress_callback and info.duration:
            progress_callback(segment.end, info.duration)

    return segments
