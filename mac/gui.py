#!/usr/bin/env python3
"""VTT GUI (Mac) — CLIを使わずに使えるウィンドウアプリ

mac/vtt.py（音声→文字起こし）と mac/slides.py（映像→スライドOCR）を、URLを貼るか
ファイルをドラッグ&ドロップしてボタンを押すだけで実行できるGUIラッパー。

- ドラッグ&ドロップ: `pip install tkinterdnd2` が入っていれば有効（無くても起動はする）
- 結果プレビュー: 実行後、文字起こし/スライドの結果を「結果」タブに表示

起動:
  python3 mac/gui.py
  （Finderからは vtt.command をダブルクリック、または .app をDock/Launchpadから）
"""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import (BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, BooleanVar,
                     StringVar, X, filedialog, messagebox, ttk)
from tkinter.scrolledtext import ScrolledText

try:  # ドラッグ&ドロップ（任意依存）
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:  # noqa: BLE001
    HAS_DND = False

HERE = Path(__file__).resolve().parent
OUT_RE = re.compile(r"→\s*(\S+\.(?:txt|md))")


class App:
    def __init__(self, root) -> None:
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue[str] = queue.Queue()
        self.outputs: list[Path] = []
        self.url = StringVar()
        self.file_path = StringVar(value="（未選択）")
        self._chosen: str | None = None
        self.lang = StringVar(value="ja")
        self.engine = StringVar(value="openaiapi")
        self.do_audio = BooleanVar(value=True)
        self.do_slides = BooleanVar(value=False)
        self.api_key = StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.status = StringVar(value="準備OK" + ("" if HAS_DND else "（D&D無効: pip install tkinterdnd2）"))
        self._build()
        self.root.after(100, self._drain)

    def _build(self) -> None:
        self.root.title("VTT — 動画まるごと文字起こし")
        self.root.geometry("660x680")
        pad = {"padx": 12, "pady": 6}

        ttk.Label(self.root, text="VTT", font=("Helvetica", 22, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        ttk.Label(self.root, text="動画の音声を文字起こし／スライドをOCRします", foreground="#666").pack(anchor="w", padx=12)

        # 入力
        src = ttk.LabelFrame(self.root, text="入力")
        src.pack(fill=X, **pad)
        row = ttk.Frame(src); row.pack(fill=X, padx=10, pady=8)
        ttk.Label(row, text="URL:").pack(side=LEFT)
        ttk.Entry(row, textvariable=self.url).pack(side=LEFT, fill=X, expand=True, padx=6)

        drop = ttk.Frame(src); drop.pack(fill=X, padx=10, pady=(0, 8))
        ttk.Button(drop, text="ファイルを選択…", command=self._pick).pack(side=LEFT)
        self.drop_zone = ttk.Label(
            drop, textvariable=self.file_path, relief="groove", anchor="center",
            foreground="#0a7", padding=8)
        self.drop_zone.pack(side=LEFT, fill=X, expand=True, padx=6)
        if HAS_DND:
            self.drop_zone.configure(text="ここに動画ファイルをドラッグ&ドロップ")
            for w in (self.root, self.drop_zone):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)

        # やること
        what = ttk.LabelFrame(self.root, text="やること")
        what.pack(fill=X, **pad)
        ttk.Checkbutton(what, text="音声を文字起こし（.txt / .srt）", variable=self.do_audio).pack(anchor="w", padx=10, pady=(8, 0))
        ttk.Checkbutton(what, text="スライドを抽出してOCR（画像 + slides.md）", variable=self.do_slides).pack(anchor="w", padx=10, pady=(0, 8))

        # 設定
        opt = ttk.LabelFrame(self.root, text="設定")
        opt.pack(fill=X, **pad)
        r = ttk.Frame(opt); r.pack(fill=X, padx=10, pady=8)
        ttk.Label(r, text="言語:").pack(side=LEFT)
        ttk.OptionMenu(r, self.lang, "ja", "ja", "en", "auto").pack(side=LEFT, padx=(4, 16))
        ttk.Label(r, text="エンジン:").pack(side=LEFT)
        ttk.OptionMenu(r, self.engine, "openaiapi", "openaiapi", "fasterwhisper").pack(side=LEFT, padx=4)
        r2 = ttk.Frame(opt); r2.pack(fill=X, padx=10, pady=(0, 8))
        ttk.Label(r2, text="OpenAI APIキー:").pack(side=LEFT)
        ttk.Entry(r2, textvariable=self.api_key, show="•").pack(side=LEFT, fill=X, expand=True, padx=6)

        # 実行
        btns = ttk.Frame(self.root); btns.pack(fill=X, **pad)
        self.run_btn = ttk.Button(btns, text="▶ 実行", command=self._run)
        self.run_btn.pack(side=LEFT)
        self.stop_btn = ttk.Button(btns, text="■ 停止", command=self._stop, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=6)
        ttk.Button(btns, text="出力フォルダを開く", command=lambda: subprocess.run(["open", str(Path.cwd())])).pack(side=RIGHT)

        # タブ: ログ / 結果
        nb = ttk.Notebook(self.root); nb.pack(fill=BOTH, expand=True, padx=12, pady=(0, 6))
        self.nb = nb
        logtab = ttk.Frame(nb); nb.add(logtab, text="ログ")
        self.log = ScrolledText(logtab, height=10, font=("Menlo", 11))
        self.log.pack(fill=BOTH, expand=True)
        self.log.configure(state=DISABLED)
        prevtab = ttk.Frame(nb); nb.add(prevtab, text="結果プレビュー")
        bar = ttk.Frame(prevtab); bar.pack(fill=X)
        ttk.Button(bar, text="保存先を開く", command=self._open_outputs).pack(side=RIGHT, pady=4)
        self.preview = ScrolledText(prevtab, height=10, font=("Hiragino Sans", 12), wrap="word")
        self.preview.pack(fill=BOTH, expand=True)

        ttk.Label(self.root, textvariable=self.status, foreground="#666", relief="sunken", anchor="w").pack(fill=X, side="bottom")

    # ---- helpers ----
    def _set_file(self, path: str) -> None:
        self._chosen = path
        self.file_path.set(Path(path).name)

    def _pick(self) -> None:
        f = filedialog.askopenfilename(
            title="動画/音声ファイルを選択",
            filetypes=[("メディア", "*.mp4 *.mov *.m4a *.mp3 *.wav *.mkv *.webm"), ("すべて", "*.*")])
        if f:
            self._set_file(f)

    def _on_drop(self, event) -> None:
        data = event.data.strip()
        # 複数/スペース入りパスは {..} で囲まれる
        m = re.findall(r"\{([^}]*)\}", data)
        path = (m[0] if m else data.split()[0]) if data else ""
        if path:
            self._set_file(path)

    def _append(self, text: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, text)
        self.log.see(END)
        self.log.configure(state=DISABLED)
        for mo in OUT_RE.finditer(text):
            p = Path(mo.group(1))
            if p not in self.outputs:
                self.outputs.append(p)

    def _open_outputs(self) -> None:
        targets = {str(p.parent if p.suffix == ".md" else p.parent) for p in self.outputs} or {str(Path.cwd())}
        for t in targets:
            subprocess.run(["open", t])

    # ---- run ----
    def _run(self) -> None:
        if not self.do_audio.get() and not self.do_slides.get():
            messagebox.showwarning("VTT", "「やること」を1つ以上選んでください。")
            return
        src_url = self.url.get().strip()
        if not src_url and not self._chosen:
            messagebox.showwarning("VTT", "URL を入力するかファイルを指定してください。")
            return

        common = ["--url", src_url] if src_url else ["--file", self._chosen]
        jobs: list[list[str]] = []
        if self.do_audio.get():
            jobs.append([sys.executable, str(HERE / "vtt.py"), *common,
                         "--language", self.lang.get(), "--engine", self.engine.get()])
        if self.do_slides.get():
            jobs.append([sys.executable, str(HERE / "slides.py"), *common])

        self.outputs.clear()
        self.preview.delete("1.0", END)
        self.run_btn.configure(state=DISABLED)
        self.stop_btn.configure(state=NORMAL)
        self.status.set("実行中…")
        self.nb.select(0)
        threading.Thread(target=self._worker, args=(jobs,), daemon=True).start()

    def _worker(self, jobs: list[list[str]]) -> None:
        env = dict(os.environ)
        if self.api_key.get().strip():
            env["OPENAI_API_KEY"] = self.api_key.get().strip()
        ok = True
        for cmd in jobs:
            name = next((Path(c).name for c in cmd if c.endswith(".py")), "job")
            self.q.put(f"\n$ {name} {' '.join(cmd[3:])}\n")
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             text=True, env=env, bufsize=1)
                assert self.proc.stdout
                for line in self.proc.stdout:
                    self.q.put(line)
                self.proc.wait()
                ok = ok and self.proc.returncode == 0
            except Exception as e:  # noqa: BLE001
                self.q.put(f"[エラー] {e}\n"); ok = False
            self.proc = None
        self.q.put(("__DONE_OK__" if ok else "__DONE_ERR__") + "\n")

    def _stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.q.put("\n[停止しました]\n")

    def _load_preview(self) -> None:
        self.preview.delete("1.0", END)
        if not self.outputs:
            self.preview.insert(END, "（出力ファイルが見つかりませんでした）")
            return
        for p in self.outputs:
            self.preview.insert(END, f"━━━ {p.name} ━━━\n")
            try:
                body = Path(p).read_text(errors="ignore")
                self.preview.insert(END, body[:20000] + ("\n…(以下略)\n" if len(body) > 20000 else "\n"))
            except Exception as e:  # noqa: BLE001
                self.preview.insert(END, f"（読み込めません: {e}）\n")
            self.preview.insert(END, "\n")

    def _drain(self) -> None:
        try:
            while True:
                line = self.q.get_nowait()
                if line.startswith("__DONE_OK__"):
                    self.status.set("完了 ✓")
                    self.run_btn.configure(state=NORMAL); self.stop_btn.configure(state=DISABLED)
                    self._load_preview(); self.nb.select(1)
                elif line.startswith("__DONE_ERR__"):
                    self.status.set("エラーで終了")
                    self.run_btn.configure(state=NORMAL); self.stop_btn.configure(state=DISABLED)
                    self._load_preview()
                else:
                    self._append(line)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main() -> None:
    root = TkinterDnD.Tk() if HAS_DND else __import__("tkinter").Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
