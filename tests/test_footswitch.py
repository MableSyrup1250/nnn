"""Exercise the real curses binary using Artemis's five terminal sequences.

Build with make, then run: python3 -m unittest discover -s tests -v
No hardware or third party Python modules are needed (Linux /proc is used).
"""
import fcntl
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import tempfile
import termios
import time
import unittest

BINARY = Path(__file__).resolve().parents[1] / 'nnn'
KEYS = {1: b'\x1b[25~', 2: b'\x1b[26~', 3: b'\x1b[28~',
        4: b'\x1b[29~', 5: b'\x1b[31~'}


class Terminal:
    def __init__(self, root, term='linux'):
        self.root = root
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 20, 100, 0, 0))
        env = dict(os.environ, TERM=term, HOME=str(root.parent),
                   XDG_CONFIG_HOME=str(root.parent / 'config'),
                   NNN_OPTS='', NNN_OPENER='', NNN_PLUG='', NNN_FIFO='')
        (root.parent / "config").mkdir(exist_ok=True)
        stub = root.parent / 'bin'
        stub.mkdir(exist_ok=True)
        nano = stub / 'nano'
        nano.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/nano-args"\n')
        nano.chmod(0o755)
        env['PATH'] = str(stub) + os.pathsep + env['PATH']
        self.process = subprocess.Popen([str(BINARY), str(root)], stdin=slave,
                                        stdout=slave, stderr=slave, env=env,
                                        start_new_session=True)
        os.close(slave)
        self.initial = self.drain()

    def drain(self):
        output = b''
        deadline = time.monotonic() + .25
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], .03)[0]:
                try:
                    output += os.read(self.master, 65536)
                except OSError:
                    break
        return output

    def press(self, *keys):
        output = b''
        for key in keys:
            os.write(self.master, KEYS[key])
            output += self.drain()
        return output

    def cwd(self):
        return Path(os.readlink(f'/proc/{self.process.pid}/cwd'))

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=5)
        os.close(self.master)


class FootswitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'files'
        self.root.mkdir()
        (self.root / 'a folder').mkdir()
        (self.root / 'b folder').mkdir()
        self.name = "c - text ' $(no shell).txt"
        (self.root / self.name).write_text('hello\n')

    def start(self, term='linux'):
        terminal = Terminal(self.root, term)
        self.addCleanup(terminal.close)
        return terminal

    def test_navigation_and_quit_on_linux_and_xterm(self):
        for term in ('linux', 'xterm-256color'):
            with self.subTest(term=term):
                t = self.start(term)
                t.press(2, 1, 4)
                self.assertEqual(t.cwd(), self.root / 'a folder')
                # Empty directory: first action is Quit.
                t.press(5, 4)
                self.assertEqual(t.process.wait(timeout=3), 0)

    def test_parent_and_navigation_cancel_action(self):
        t = self.start()
        t.press(5, 5, 5)  # Delete menu on a folder, not accepted.
        t.press(2, 4)
        self.assertEqual(t.cwd(), self.root / 'b folder')
        t.press(3)
        self.assertEqual(t.cwd(), self.root)
        self.assertTrue((self.root / 'a folder').exists())

    def test_move_to_empty_directory(self):
        t = self.start()
        t.press(2, 2, 5, 5, 4)  # text -> Select for move -> accept
        self.assertTrue((self.root / self.name).exists())
        t.press(1, 1, 4)
        self.assertEqual(t.cwd(), self.root / 'a folder')
        t.press(5, 4)  # Move here, even with no entries
        self.assertFalse((self.root / self.name).exists())
        self.assertEqual((self.root / 'a folder' / self.name).read_text(), 'hello\n')

    def test_collision_retains_source_and_can_cancel_move(self):
        destination = self.root / 'a folder' / self.name
        destination.write_text('keep me')
        t = self.start()
        t.press(2, 2, 5, 5, 4, 1, 1, 4)
        output = t.press(5, 4)
        self.assertIn(b'Destination already exists', output)
        self.assertEqual(destination.read_text(), 'keep me')
        self.assertTrue((self.root / self.name).exists())
        t.press(5, 5, 4)  # Cancel move
        output = t.press(5)
        self.assertIn(b'Open in nano', output)

    def test_delete_requires_confirmation_and_can_cancel(self):
        t = self.start()
        t.press(2, 2, 5, 5, 5, 4)
        self.assertTrue((self.root / self.name).exists())
        t.press(5)  # Cancel confirmation
        self.assertTrue((self.root / self.name).exists())
        t.press(5, 5, 5, 4, 4)
        self.assertFalse((self.root / self.name).exists())

    def test_recursive_directory_delete(self):
        (self.root / 'a folder' / 'child').write_text('contents')
        t = self.start()
        t.press(5, 5, 5, 4, 4)
        self.assertFalse((self.root / 'a folder').exists())

    def test_open_text_and_empty_file_in_nano(self):
        t = self.start()
        t.press(2, 2, 5, 4)
        args = (self.root.parent / 'nano-args').read_text().splitlines()
        self.assertEqual(args, ['--', str(self.root / self.name)])
        (self.root / self.name).write_text('')
        t.press(5, 4)
        self.assertEqual((self.root.parent / 'nano-args').read_text().splitlines(), args)

    def test_fragmented_switch_sequence(self):
        t = self.start()
        for byte in KEYS[2]:
            os.write(t.master, bytes([byte]))
            time.sleep(.06)
        t.drain()
        t.press(4)
        self.assertEqual(t.cwd(), self.root / 'b folder')

    def test_move_directory(self):
        (self.root / 'a folder' / 'child').write_text('nested')
        t = self.start()
        t.press(5, 5, 4, 2, 4, 5, 4)
        self.assertFalse((self.root / 'a folder').exists())
        self.assertEqual((self.root / 'b folder' / 'a folder' / 'child').read_text(), 'nested')

    def test_move_source_disappeared(self):
        t = self.start()
        t.press(2, 2, 5, 5, 4, 1, 1, 4)
        (self.root / self.name).unlink()
        output = t.press(5, 4)
        self.assertIn(b'Move source changed or disappeared', output)
        self.assertFalse((self.root / 'a folder' / self.name).exists())

    def test_reject_binary_file(self):
        (self.root / self.name).write_bytes(b'\x00\x01binary')
        t = self.start()
        output = t.press(2, 2, 5, 4)
        self.assertIn(b'Nano supports readable text files only', output)
        self.assertFalse((self.root.parent / 'nano-args').exists())


if __name__ == '__main__':
    unittest.main()
