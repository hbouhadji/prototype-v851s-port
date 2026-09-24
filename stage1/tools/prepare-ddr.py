#!/usr/bin/env python3
"""Extract xfel's V85x SRAM DDR initializer; use this device's boot0 parameters."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

source, firmware, output = map(Path, sys.argv[1:])
b = firmware.read_bytes()
assert b[4:12] == b'eGON.BT0'
size = struct.unpack_from('<I', b, 16)[0]
words = list(struct.unpack('<%dI' % (size // 4), b[:size]))
expected = words[3]
words[3] = 0x5f0a6c39
assert sum(words) & 0xffffffff == expected, 'Invalid boot0 checksum'
src = source.read_text().split('static const uint8_t ddr_payload[] = {', 1)[1].split('};', 1)[0]
payload = bytearray(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})\b', src))
assert payload[4:12] == b'eGON.BT0'
assert struct.unpack_from('<I', payload, 16)[0] == len(payload)
payload[0x38:0x98] = b[0x38:0x98]
struct.pack_into('<I', payload, 12, 0x5f0a6c39)
checksum = sum(struct.unpack('<%dI' % (len(payload) // 4), payload)) & 0xffffffff
struct.pack_into('<I', payload, 12, checksum)
output.write_bytes(payload)
output.with_suffix('.json').write_text(json.dumps({
    'firmware_sha256': hashlib.sha256(b).hexdigest(),
    'xfel_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'payload_sha256': hashlib.sha256(payload).hexdigest(),
    'load_address': '0x00028000', 'size': len(payload),
    'dram_parameters': ['0x%08x' % v for v in struct.unpack_from('<24I', b, 0x38)],
}, indent=2) + '\n')
print('Prepared DDR initializer:', len(payload), 'bytes')
