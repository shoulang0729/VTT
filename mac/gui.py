#!/usr/bin/env python3
"""VTT GUI (Mac) — CLIを使わずに使えるウィンドウアプリ

mac/vtt.py（音声→文字起こし）と mac/slides.py（映像→スライドOCR）を、URLを貼って
ボタンを押すだけで実行できるGUIラッパー。Python標準の Tkinter のみ使用（追加インストール不要）。

起動:
  python3 mac/gui.py
  （Finderからは vtt.command をダブルクリックでもOK）
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import (BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, StringVar, Tk,
                     BooleanVar, X, filedialog, messagebox, ttk)
from tkinter.scrolledtext import ScrolledText

HERE = Path(__file__).resolve().parent


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue[str] = queue.Queue()
        self.file_path = StringVar()
        self.url = StringVar()
        self.lang = StringVar(value="ja")
        self.engine = StringVar(value="openaiapi")
        self.do_audio = BooleanVar(value=True)
        self.do_slides = BooleanVar(value=False)
        self.api_key = StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.cookies = StringVar(value="（なし）")
        self.status = StringVar(value="準備OK")
        self._build()
        self.root.after(100, self._drain)

    def _build(self) -> None:
        self.root.title("VTT — 動画まるごと文字起こし")
        self.root.geometry("620x600")
        pad = {"padx": 12, "pady": 6}

        head = ttk.Label(self.root, text="VTT",
                         font=("Helvetica", 22, "bold"))
        head.pack(anchor="w", padx=12, pady=(12, 0))
        ttk.Label(self.root, text="動画の音声を文字起こし／スライドをOCRします",
                  foreground="#666").pack(anchor="w", padx=12)

        # --- 入力ソース ---
        src = ttk.LabelFrame(self.root, text="入力")
        src.pack(fill=X, **pad)
        row = ttk.Frame(src); row.pack(fill=X, padx=10, pady=8)
        ttk.Label(row, text="URL:").pack(side=LEFT)
        ttk.Entry(row, textvariable=self.url).pack(side=LEFT, fill=X, expand=True, padx=6)
        row2 = ttk.Frame(src); row2.pack(fill=X, padx=10, pady=(0, 8))
        ttk.Label(row2, text="または").pack(side=LEFT)
        ttk.Button(row2, text="ファイルを選択…", command=self._pick).pack(side=LEFT, padx=6)
        ttk.Label(row2, textvariable=self.file_path, foreground="#0a7").pack(side=LEFT)

        # --- やること ---
        what = ttk.LabelFrame(self.root, text="やること")
        what.pack(fill=X, **pad)
        ttk.Checkbutton(what, text="音声を文字起こし（.txt / .srt）",
                        variable=self.do_audio).pack(anchor="w", padx=10, pady=(8, 0))
        ttk.Checkbutton(what, text="スライドを抽出してOCR（画像 + slides.md）",
                        variable=self.do_slides).pack(anchor="w", padx=10, pady=(0, 8))

        # --- 設定 ---
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

        # --- 実行 ---
        btns = ttk.Frame(self.root); btns.pack(fill=X, **pad)
        self.run_btn = ttk.Button(btns, text="▶ 実行", command=self._run)
        self.run_btn.pack(side=LEFT)
        self.stop_btn = ttk.Button(btns, text="■ 停止", command=self._stop, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=6)
        ttk.Button(btns, text="出力フォルダを開く",
                   command=lambda: subprocess.run(["open", str(Path.cwd())])).pack(side=RIGHT)

        # --- ログ ---
        self.log = ScrolledText(self.root, height=12, font=("Menlo", 11))
        self.log.pack(fill=BOTH, expand=True, padx=12, pady=(0, 6))
        self.log.configure(state=DISABLED)

        ttk.Label(self.root, textvariable=self.status, foreground="#666",
                  relief="sunken", anchor="w").pack(fill=X, side="bottom")

    # ---- actions ----
    def _pick(self) -> None:
        f = filedialog.askopenfilename(
            title="動画/音声ファイルを選択",
            filetypes=[("メディア", "*.mp4 *.mov *.m4a *.mp3 *.wav *.mkv *.webm"), ("すべて", "*.*")])
        if f:
            self.file_path.set(Path(f).name)
            self._chosen = f

    def _append(self, text: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, text)
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _run(self) -> None:
        if not self.do_audio.get() and not self.do_slides.get():
            messagebox.showwarning("VTT", "「やること」を1つ以上選んでください。")
            return
        src_url = self.url.get().strip()
        src_file = getattr(self, "_chosen", None)
        if not src_url and not src_file:
            messagebox.showwarning("VTT", "URL を入力するかファイルを選択してください。")
            return

        jobs: list[list[str]] = []
        common: list[str] = []
        if src_url:
            common += ["--url", src_url]
        else:
            common += ["--file", src_file]

        if self.do_audio.get():
            cmd = [sys.executable, str(HERE / "vtt.py"), *common,
                   "--language", self.lang.get(), "--engine", self.engine.get()]
            jobs.append(cmd)
        if self.do_slides.get():
            cmd = [sys.executable, str(HERE / "slides.py"), *common]
            jobs.append(cmd)

        self.run_btn.configure(state=DISABLED)
        self.stop_btn.configure(state=NORMAL)
        self.status.set("実行中…")
        threading.Thread(target=self._worker, args=(jobs,), daemon=True).start()

    def _worker(self, jobs: list[list[str]]) -> None:
        env = dict(os.environ)
        if self.api_key.get().strip():
            env["OPENAI_API_KEY"] = self.api_key.get().strip()
        ok = True
        for cmd in jobs:
            self.q.put(f"\n$ {' '.join(Path(c).name if c.endswith('.py') else c for c in cmd)}\n")
            try:
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, bufsize=1)
                assert self.proc.stdout
                for line in self.proc.stdout:
                    self.q.put(line)
                self.proc.wait()
                if self.proc.returncode != 0:
                    ok = False
            except Exception as e:  # noqa: BLE001
                self.q.put(f"[エラー] {e}\n")
                ok = False
            self.proc = None
        self.q.put(("__DONE_OK__" if ok else "__DONE_ERR__") + "\n")

    def _stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.q.put("\n[停止しました]\n")

    def _drain(self) -> None:
        try:
            while True:
                line = self.q.get_nowait()
                if line.startswith("__DONE_OK__"):
                    self.status.set("完了 ✓")
                    self.run_btn.configure(state=NORMAL)
                    self.stop_btn.configure(state=DISABLED)
                elif line.startswith("__DONE_ERR__"):
                    self.status.set("エラーで終了")
                    self.run_btn.configure(state=NORMAL)
                    self.stop_btn.configure(state=DISABLED)
                else:
                    self._append(line)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
