import ffmpeg
from pathlib import Path


def _ts_label(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}_{m:02d}_{s:02d}"


def extract_snapshots(
    video_path: Path,
    output_dir: Path,
    interval: int = 60,
) -> list[tuple[int, Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    probe = ffmpeg.probe(str(video_path))
    duration = float(probe["format"]["duration"])

    snapshots = []
    for ts in range(interval, int(duration), interval):
        output_path = output_dir / f"snapshot_{_ts_label(ts)}.jpg"
        try:
            (
                ffmpeg
                .input(str(video_path), ss=ts)
                .video
                .output(str(output_path), vframes=1, **{"q:v": 2})
                .overwrite_output()
                .run(quiet=True)
            )
            if output_path.exists():
                snapshots.append((ts, output_path))
        except ffmpeg.Error:
            pass

    return snapshots
