#!/usr/bin/env python3
"""Use the dumped boot0 DDR routine in SRAM, without executing its boot path."""
import hashlib
import json
import struct
from pathlib import Path

base = Path(__file__).resolve().parents[1]
backup = base / 'out/boot0-fel-backup-20260924.bin'
raw = backup.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '62f10f397bda47111e2d0df5c1887c7bf9155d76ca71ff890767e2774afe8f0d'
size = struct.unpack_from('<I', raw, 16)[0]
assert size == 0xb000
payload = bytearray(raw[:size])
assert payload[0x4cbc:0x4cc0] == bytes.fromhex('38b50c46')

def patch(offset, expected, replacement):
    expected, replacement = bytes.fromhex(expected), bytes.fromhex(replacement)
    assert len(expected) == len(replacement)
    assert payload[offset:offset + len(expected)] == expected
    payload[offset:offset + len(expected)] = replacement

patch(0x2b5c, '034b1b685a695206', 'dff800f001d00200')
# Suppress the standby resume path; DDR setup/test and return remain intact.
patch(0x4e50, 'fef730fb', '00bf00bf')
(base / 'out/ddr-native.bin').write_bytes(payload)
(base / 'out/ddr-native.json').write_text(json.dumps({
    'source_backup_sha256': hashlib.sha256(raw).hexdigest(),
    'payload_sha256': hashlib.sha256(payload).hexdigest(),
    'load_address': '0x20000', 'entry_called': '0x24cbd',
    'bss_clear_called': '0x20408', 'boot0_main_called': False,
    'parameters_modified': False,
}, indent=2) + '\n')
print('Native DDR-only image prepared; boot0 startup/main are not called.')
