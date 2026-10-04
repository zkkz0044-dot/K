from __future__ import annotations
import io, os, pty, termios, unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from kk_k.console import MAX_RAW_LINE_BYTES, _decode_console_bytes, _disable_vquit_if_tty, _read_console_line, _restore_tty
from kk_k.human_ingress import HumanIngressError

class _FakeStdin:
    def __init__(self,data:bytes):
        self.buffer=io.BytesIO(data)

class FKP03ConsoleEncodingTests(unittest.TestCase):
    def test_utf8_chinese(self):
        self.assertEqual(_decode_console_bytes('你好K'.encode('utf-8')),'你好K')

    def test_windows_gb18030_chinese(self):
        self.assertEqual(_decode_console_bytes('你好K'.encode('gb18030')),'你好K')

    def test_invalid_bytes_fail_closed(self):
        with self.assertRaises(HumanIngressError):
            _decode_console_bytes(b'\xff\xff\xff')

    def test_crlf_is_removed_after_windows_decode(self):
        fake=_FakeStdin('你好K\r\n'.encode('gb18030'))
        with patch('kk_k.console.sys.stdin',fake), redirect_stdout(io.StringIO()):
            self.assertEqual(_read_console_line('you> '),'你好K')

    def test_oversize_raw_line_rejected(self):
        fake=_FakeStdin((b'a'*(MAX_RAW_LINE_BYTES+1))+b'\n')
        with patch('kk_k.console.sys.stdin',fake), redirect_stdout(io.StringIO()):
            with self.assertRaises(HumanIngressError):
                _read_console_line('you> ')

    def test_vquit_only_is_disabled_on_tty(self):
        master,slave=pty.openpty()
        try:
            before=termios.tcgetattr(slave)
            self.assertEqual(before[6][termios.VQUIT], b'\x1c')
            saved=_disable_vquit_if_tty(slave)
            after=termios.tcgetattr(slave)
            self.assertEqual(after[6][termios.VQUIT], bytes([os.fpathconf(slave,'PC_VDISABLE')]))
            self.assertEqual(after[6][termios.VINTR], before[6][termios.VINTR])
            _restore_tty(slave,saved)
            restored=termios.tcgetattr(slave)
            self.assertEqual(restored[6][termios.VQUIT], before[6][termios.VQUIT])
        finally:
            os.close(master); os.close(slave)

    def test_disabled_vquit_byte_reaches_reader_instead_of_signal(self):
        master,slave=pty.openpty()
        saved=_disable_vquit_if_tty(slave)
        try:
            os.write(master,b'abc\x1cdef\n')
            raw=os.read(slave,128)
            self.assertEqual(raw,b'abc\x1cdef\n')
        finally:
            _restore_tty(slave,saved); os.close(master); os.close(slave)

if __name__=='__main__': unittest.main()
