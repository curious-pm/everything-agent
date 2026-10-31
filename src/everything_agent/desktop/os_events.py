"""Stops Reachy cleanly when the OS shuts down, restarts or logs out, or the console is closed."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from typing import Callable

logger = logging.getLogger(__name__)

WINDOW_CLASS = "EverythingAgentSessionWatcher"
_POSIX_SIGNALS = {getattr(signal, name) for name in ("SIGTERM", "SIGINT", "SIGHUP") if hasattr(signal, name)}

_live_ctypes_callbacks: list = []


def prepare() -> None:
    """Call first thing in main(), before any thread starts, so every thread inherits the signal mask."""
    if sys.platform != "win32":
        signal.pthread_sigmask(signal.SIG_BLOCK, _POSIX_SIGNALS)


def install(stop_blocking: Callable[[], None], quit_async: Callable[[], None]) -> None:
    """``stop_blocking`` runs on session end (returns once Reachy is stopped); ``quit_async`` on Ctrl+C."""
    if sys.platform == "win32":
        _install_console_handler(stop_blocking, quit_async)
        threading.Thread(target=_session_window, args=(stop_blocking,), name="session-watch", daemon=True).start()
    else:
        threading.Thread(target=_wait_for_signal, args=(stop_blocking,), name="signal-watch", daemon=True).start()


def _wait_for_signal(stop_blocking: Callable[[], None]) -> None:
    sig = signal.sigwait(_POSIX_SIGNALS)
    logger.info("Received %s, stopping Reachy", signal.Signals(sig).name)
    stop_blocking()


def _install_console_handler(stop_blocking: Callable[[], None], quit_async: Callable[[], None]) -> None:
    import ctypes
    from ctypes import wintypes

    ctrl_c, ctrl_break, ctrl_close, ctrl_logoff, ctrl_shutdown = 0, 1, 2, 5, 6

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    def on_ctrl(event: int) -> bool:
        if event in (ctrl_c, ctrl_break):
            quit_async()
            return True
        if event in (ctrl_close, ctrl_logoff, ctrl_shutdown):
            stop_blocking()
            return True
        return False

    _live_ctypes_callbacks.append(on_ctrl)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(on_ctrl, True)


def _session_window(stop_blocking: Callable[[], None]) -> None:
    """A hidden top-level window: only those receive WM_QUERYENDSESSION / WM_ENDSESSION."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lresult = ctypes.c_ssize_t
    wndproc_t = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT), ("lpfnWndProc", wndproc_t), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
        ]

    user32.DefWindowProcW.restype = lresult
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.ShutdownBlockReasonCreate.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
    user32.ShutdownBlockReasonDestroy.argtypes = [wintypes.HWND]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    wm_queryendsession, wm_endsession = 0x0011, 0x0016

    def window_proc(hwnd, msg, wparam, lparam):
        if msg == wm_queryendsession:
            user32.ShutdownBlockReasonCreate(hwnd, "Putting Reachy to sleep")
            return 1
        if msg == wm_endsession:
            session_is_ending = bool(wparam)
            if session_is_ending:
                logger.info("Windows is ending the session, stopping Reachy")
                try:
                    stop_blocking()
                except Exception:
                    logger.exception("Stopping at session end failed")
            user32.ShutdownBlockReasonDestroy(hwnd)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = wndproc_t(window_proc)
    _live_ctypes_callbacks.append(proc)
    hinstance = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW(lpfnWndProc=proc, hInstance=hinstance, lpszClassName=WINDOW_CLASS)
    if not user32.RegisterClassW(ctypes.byref(wc)):
        logger.error("Could not register the session window (error %d)", ctypes.get_last_error())
        return
    hwnd = user32.CreateWindowExW(0, WINDOW_CLASS, "Everything Agent", 0, 0, 0, 0, 0, None, None, hinstance, None)
    if not hwnd:
        logger.error("Could not create the session window (error %d)", ctypes.get_last_error())
        return

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
