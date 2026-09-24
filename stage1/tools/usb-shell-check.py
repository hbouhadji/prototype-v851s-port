#!/usr/bin/env python3
"""Wait for one new macOS USB ACM port and capture stage1 shell evidence."""
import glob
import os
from pathlib import Path
import secrets
import select
import termios
import time
import tty

log = Path(__file__).resolve().parents[1] / 'logs' / 'usb-shell.log'
old_ports = set(glob.glob('/dev/cu.usbmodem*'))
deadline = time.monotonic() + 60
fd = None
while time.monotonic() < deadline:
    ports = set(glob.glob('/dev/cu.usbmodem*')) - old_ports
    if len(ports) > 1:
        raise SystemExit('Several new ACM ports; identify the dongle before sending commands')
    if ports:
        port = ports.pop()
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(fd)
        attrs = termios.tcgetattr(fd)
        attrs[4] = attrs[5] = termios.B115200
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        print(f'Opened {port}', flush=True)
        break
    time.sleep(0.25)
if fd is None:
    raise SystemExit('No new USB ACM port within 60 seconds')

nonce = secrets.token_hex(8)
# Only read Linux state; the challenge must be expanded by the remote shell.
commands = ("uname -a; cat /proc/meminfo; cat /proc/cmdline; "
            "dmesg; printf 'SHELL_PROOF_%s\\n' '" + nonce + "'\n")
data = bytearray()
try:
    time.sleep(1)
    os.write(fd, ('\n' + commands).encode())
    end = time.monotonic() + 20
    while time.monotonic() < end:
        if select.select([fd], [], [], 1)[0]:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            print(chunk.decode(errors='replace'), end='', flush=True)
            if ('SHELL_PROOF_' + nonce).encode() in data and b'Linux' in data:
                break
finally:
    os.close(fd)
    log.write_bytes(data)
if ('SHELL_PROOF_' + nonce).encode() not in data or b'Linux' not in data:
    raise SystemExit('USB enumerated, but a Linux shell response was not verified')
print(f'\nLinux shell verified; transcript: {log}', flush=True)
