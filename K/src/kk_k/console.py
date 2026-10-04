from __future__ import annotations
import argparse, os, sys, termios
from .chat_runtime import ChatRuntimeError, run_turn
from .human_ingress import HumanIngressError, parse_console_line, parse_paste_text

BANNER = "K local console — cognitive dialogue only. Execution/approval is disabled in FKP03."
HELP = "Plain text=CHAT | /ask TEXT | /plan TEXT | /remember TEXT | /paste | /help | /quit"
PASTE_HELP = "Paste mode: paste the full multiline text, then enter .end on a line by itself."
MAX_RAW_LINE_BYTES = 12288


def _disable_vquit_if_tty(fd: int = 0):
    """Disable only the terminal VQUIT control byte; preserve other tty signals."""
    if not os.isatty(fd):
        return None
    try:
        attrs = termios.tcgetattr(fd)
        original = list(attrs)
        original[6] = list(attrs[6])
        disabled = os.fpathconf(fd, "PC_VDISABLE")
        attrs[6][termios.VQUIT] = bytes([disabled])
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        return original
    except (OSError, termios.error, ValueError):
        raise HumanIngressError("console tty VQUIT hardening failed")


def _restore_tty(fd: int, attrs) -> None:
    if attrs is None:
        return
    try:
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except (OSError, termios.error):
        pass


def _decode_console_bytes(raw: bytes) -> str:
    if not isinstance(raw, bytes):
        raise HumanIngressError("console input must be bytes")
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding, "strict")
        except UnicodeDecodeError:
            continue
    raise HumanIngressError("console input encoding is neither UTF-8 nor GB18030")


def _read_console_line(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    raw = sys.stdin.buffer.readline(MAX_RAW_LINE_BYTES + 2)
    if raw == b"":
        raise EOFError
    if len(raw) > MAX_RAW_LINE_BYTES + 1 or (
        len(raw) > MAX_RAW_LINE_BYTES and not raw.endswith(b"\n")
    ):
        while raw and not raw.endswith(b"\n"):
            raw = sys.stdin.buffer.readline(MAX_RAW_LINE_BYTES + 2)
        raise HumanIngressError("console line too large")
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    if len(raw) > MAX_RAW_LINE_BYTES:
        raise HumanIngressError("console line too large")
    return _decode_console_bytes(raw)


def handle(text: str) -> str:
    msg = parse_console_line(text)
    return run_turn(msg)


def handle_paste(text: str) -> str:
    msg = parse_paste_text(text)
    return run_turn(msg)


def _read_paste() -> str:
    print(PASTE_HELP)
    lines = []
    while True:
        try:
            line = _read_console_line("... ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise HumanIngressError("paste cancelled")
        if line == ".end":
            break
        lines.append(line)
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--once")
    a = p.parse_args(argv)
    if a.once is not None:
        try:
            print(handle(a.once))
            return 0
        except (HumanIngressError, ChatRuntimeError) as exc:
            print("K ERROR:", str(exc), file=sys.stderr)
            return 2
    print(BANNER)
    print(HELP)
    tty_attrs = _disable_vquit_if_tty(0)
    try:
        while True:
            try:
                line = _read_console_line("you> ")
            except HumanIngressError as exc:
                print("K INPUT REJECTED:", exc)
                continue
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            stripped = line.strip()
            if stripped == "/quit":
                return 0
            if stripped == "/help":
                print(HELP)
                continue
            try:
                if stripped == "/paste":
                    text = _read_paste()
                    print("K>", handle_paste(text))
                else:
                    print("K>", handle(line))
            except HumanIngressError as exc:
                print("K INPUT REJECTED:", exc)
            except ChatRuntimeError as exc:
                print("K UNAVAILABLE:", exc)
    finally:
        _restore_tty(0, tty_attrs)


if __name__ == "__main__":
    raise SystemExit(main())
