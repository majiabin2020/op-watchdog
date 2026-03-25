# ui/main_window.py
import threading
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

from config import APP_NAME, APP_VERSION, MONITOR_INTERVAL
from core.watchdog import WatchdogState


# ── Colour palette ────────────────────────────────────────────────────
BG = "#0d1117"
BG2 = "#161b22"
BORDER = "#21262d"
BORDER2 = "#30363d"
GREEN = "#3fb950"
RED = "#ff7b72"
YELLOW = "#e8b84b"
GREY = "#8b949e"
BLUE = "#58a6ff"
FONT_MONO = ("Courier New", 10)
FONT_MONO_SM = ("Courier New", 9)
FONT_TITLE = ("Courier New", 11, "bold")


class MainWindow:
    def __init__(
        self,
        on_start: Callable,
        on_stop: Callable,
        on_hide: Callable,
        on_exit: Callable,
    ):
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_hide = on_hide
        self._on_exit = on_exit

        self._root = tk.Tk()
        self._state = WatchdogState.STOPPED
        self._restart_count = 0
        self._countdown = MONITOR_INTERVAL
        self._countdown_job = None

        self._build_ui()
        self._root.protocol("WM_DELETE_WINDOW", self._on_hide)  # ✕ → hide, not quit

    # ── Build UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = self._root
        root.title(APP_NAME)
        root.configure(bg=BG)
        root.resizable(False, False)
        root.geometry("480x520")

        # ── Title bar ─────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg=BG2, pady=8)
        title_frame.pack(fill=tk.X)

        tk.Label(title_frame, text="🦞", bg=BG2, fg=GREEN,
                 font=("", 14)).pack(side=tk.LEFT, padx=(12, 4))
        tk.Label(title_frame, text=APP_NAME, bg=BG2, fg=BLUE,
                 font=FONT_TITLE).pack(side=tk.LEFT)

        btn_frame = tk.Frame(title_frame, bg=BG2)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_frame, text="●", bg=BG2, fg="#febc2e", bd=0,
                  activebackground=BG2, cursor="hand2",
                  command=self._on_hide).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="●", bg=BG2, fg="#ff5f57", bd=0,
                  activebackground=BG2, cursor="hand2",
                  command=self._on_hide).pack(side=tk.LEFT)

        tk.Frame(root, bg=BORDER2, height=1).pack(fill=tk.X)

        # ── Status area ───────────────────────────────────────────────
        status_frame = tk.Frame(root, bg=BG, pady=12, padx=16)
        status_frame.pack(fill=tk.X)

        # Gateway status column
        gw_col = tk.Frame(status_frame, bg=BG)
        gw_col.pack(side=tk.LEFT)
        tk.Label(gw_col, text="网关状态", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.W)
        status_row = tk.Frame(gw_col, bg=BG)
        status_row.pack(anchor=tk.W)
        self._status_dot = tk.Label(status_row, text="●", bg=BG, fg=RED,
                                    font=("Courier New", 12))
        self._status_dot.pack(side=tk.LEFT)
        self._status_label = tk.Label(status_row, text="离线", bg=BG, fg=RED,
                                      font=("Courier New", 12, "bold"))
        self._status_label.pack(side=tk.LEFT, padx=(4, 0))

        # Right side status columns
        check_col = tk.Frame(status_frame, bg=BG)
        check_col.pack(side=tk.RIGHT, padx=(0, 20))
        self._restart_val = tk.Label(check_col, text="0", bg=BG, fg=BLUE,
                                     font=("Courier New", 11, "bold"))
        self._restart_val.pack(anchor=tk.E)
        tk.Label(check_col, text="重启次数", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.E)

        countdown_col = tk.Frame(status_frame, bg=BG)
        countdown_col.pack(side=tk.RIGHT, padx=(0, 24))
        self._countdown_val = tk.Label(countdown_col, text="--:--", bg=BG,
                                       fg=YELLOW, font=("Courier New", 11, "bold"))
        self._countdown_val.pack(anchor=tk.E)
        tk.Label(countdown_col, text="下次检查", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.E)

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Log area ──────────────────────────────────────────────────
        log_frame = tk.Frame(root, bg=BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        self._log_text = tk.Text(
            log_frame, bg=BG, fg=GREEN, font=FONT_MONO_SM,
            state=tk.DISABLED, wrap=tk.WORD, bd=0,
            selectbackground="#264f78",
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview,
                                 bg=BG2, troughcolor=BG)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure text tags for colours
        self._log_text.tag_configure("green", foreground=GREEN)
        self._log_text.tag_configure("red", foreground=RED)
        self._log_text.tag_configure("yellow", foreground=YELLOW)
        self._log_text.tag_configure("grey", foreground=GREY)
        self._log_text.tag_configure("timestamp", foreground="#555555")

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Buttons ───────────────────────────────────────────────────
        btn_area = tk.Frame(root, bg=BG, pady=12, padx=16)
        btn_area.pack(fill=tk.X)

        self._start_btn = tk.Button(
            btn_area, text="[ 开始看门 ]",
            bg=GREEN, fg=BG, font=FONT_MONO, bd=0,
            activebackground="#2ea043", cursor="hand2",
            command=self._handle_start,
        )
        self._start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self._stop_btn = tk.Button(
            btn_area, text="[ 关闭看门 ]",
            bg=BG, fg="#444c56", font=FONT_MONO, bd=0,
            relief=tk.SOLID, activebackground=BG2, cursor="hand2",
            command=self._handle_stop,
        )
        self._stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Footer ────────────────────────────────────────────────────
        footer = tk.Frame(root, bg=BG2, pady=4)
        footer.pack(fill=tk.X)
        tk.Label(footer, text=f"v{APP_VERSION}", bg=BG2, fg="#444c56",
                 font=FONT_MONO_SM).pack(side=tk.LEFT, padx=10)
        self._footer_label = tk.Label(
            footer, text="等待启动", bg=BG2, fg="#444c56", font=FONT_MONO_SM
        )
        self._footer_label.pack(side=tk.RIGHT, padx=10)

    # ── Button handlers ───────────────────────────────────────────────

    def _handle_start(self):
        self._on_start()
        self.hide()

    def _handle_stop(self):
        self._on_stop()

    # ── Public API (called by watchdog callbacks) ──────────────────────

    def on_state_change(self, state: WatchdogState) -> None:
        """Thread-safe: schedule UI update on main thread."""
        self._root.after(0, self._apply_state, state)

    def _apply_state(self, state: WatchdogState) -> None:
        self._state = state
        if state == WatchdogState.RUNNING:
            self._status_dot.config(fg=GREEN)
            self._status_label.config(text="在线", fg=GREEN)
            self._footer_label.config(text="监控中 · 已缩小到托盘后持续运行")
            self._start_countdown()
        elif state == WatchdogState.STARTING:
            self._status_dot.config(fg=YELLOW)
            self._status_label.config(text="启动中", fg=YELLOW)
            self._stop_countdown()
        elif state == WatchdogState.RESTARTING:
            self._status_dot.config(fg=YELLOW)
            self._status_label.config(text="重启中", fg=YELLOW)
            self._stop_countdown()
        elif state == WatchdogState.STOPPED:
            self._status_dot.config(fg=RED)
            self._status_label.config(text="离线", fg=RED)
            self._footer_label.config(text="监控已停止")
            self._stop_countdown()

    def on_restart_count(self, count: int) -> None:
        self._root.after(0, self._restart_val.config, {"text": str(count)})

    def append_log(self, message: str) -> None:
        """Thread-safe log append."""
        self._root.after(0, self._do_append_log, message)

    def _do_append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        tag = "grey"
        if "✓" in message or "成功" in message or "正常" in message:
            tag = "green"
        elif "✗" in message or "失败" in message or "异常" in message or "错误" in message:
            tag = "red"
        elif "⚡" in message or "正在" in message or "尝试" in message or "重启" in message:
            tag = "yellow"

        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{ts}] ", "timestamp")
        self._log_text.insert(tk.END, message + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    # ── Countdown timer ───────────────────────────────────────────────

    def _start_countdown(self) -> None:
        self._countdown = MONITOR_INTERVAL
        self._tick_countdown()

    def _stop_countdown(self) -> None:
        if self._countdown_job:
            self._root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self._countdown_val.config(text="--:--")

    def _tick_countdown(self) -> None:
        if self._state != WatchdogState.RUNNING:
            return
        mins, secs = divmod(self._countdown, 60)
        self._countdown_val.config(text=f"{mins:02d}:{secs:02d}")
        if self._countdown > 0:
            self._countdown -= 1
            self._countdown_job = self._root.after(1000, self._tick_countdown)
        else:
            self._countdown = MONITOR_INTERVAL
            self._tick_countdown()

    # ── Window management ─────────────────────────────────────────────

    def show(self) -> None:
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def hide(self) -> None:
        self._root.withdraw()

    def get_root(self) -> tk.Tk:
        """Return the tk.Tk root — used by TrayManager for main_thread_dispatch."""
        return self._root

    def run(self) -> None:
        self._root.mainloop()
