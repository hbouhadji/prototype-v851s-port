#!/usr/bin/env python3
"""Instrument only the known xfel FES image; retain the original alongside it."""
import struct
from pathlib import Path

out = Path(__file__).resolve().parents[1] / 'out'
payload = bytearray((out / 'ddr-stock.bin').read_bytes())

def patch(address, expected, replacement):
    offset = address - 0x28000
    expected, replacement = bytes.fromhex(expected), bytes.fromhex(replacement)
    assert len(expected) == len(replacement)
    assert payload[offset:offset + len(expected)] == expected, hex(address)
    payload[offset:offset + len(expected)] = replacement

# Do not initialize UART pins or clocks. Character output goes to SRAM instead.
patch(0x2be42, 'fdf7e5fa', '00bf00bf')
# Thumb LDR.W PC, [PC, #0], followed by the Thumb logger address 0x2d001.
patch(0x29464, '034b1b685a695206', 'dff800f001d00200')
# The explicit failure loop returns zero through the existing epilogue.
# This does not resolve any unbounded hardware polling elsewhere in the image.
patch(0x2be98, 'fee7', 'f6e7')
def save(name):
    struct.pack_into('<I', payload, 12, 0x5f0a6c39)
    checksum = sum(struct.unpack('<%dI' % (len(payload) // 4), payload)) & 0xffffffff
    struct.pack_into('<I', payload, 12, checksum)
    (out / name).write_bytes(payload)

save('ddr-instrumented.bin')
# Return sentinel 1 after the banner, before platform/clock/DDR setup.
patch(0x2be50, 'fdf742f8', '012419e0')
save('ddr-preflight.bin')
# Keep the running FEL CPU/peripheral clocks and platform power configuration.
# MOVS r0, #0 substitutes the successful platform-init result, then continue.
patch(0x2be50, '012419e0', '002000bf')
save('ddr-inherited-clocks.bin')
inherited = bytes(payload)
def branch_to(address, target):
    offset = target - (address + 4)
    assert 0 <= offset < (1 << 20) and offset % 2 == 0
    return struct.pack('<HH', 0xf000 | ((offset >> 12) & 0x3ff),
                       0xb800 | ((offset >> 1) & 0x7ff)).hex()

def bound_polls():
    patch(0x2abb0, '2368db00fcd5', branch_to(0x2abb0, 0x2d400) + '00bf')
    for index, (address, expected) in enumerate([
        (0x2b0b6, 'd8f80030da07fbd5'),
        (0x2b0e2, 'd8f80030d807fbd5'),
        (0x2b112, '136803f00703032bfad1'),
        (0x2b134, 'd9f8003003f00703012bf9d1'),
        (0x2b16c, 'd8f80030da07fbd5'),
        (0x2b230, '1368db07fcd5'),
    ]):
        patch(address, expected, branch_to(address, 0x2d500 + index * 128)
              + '00bf' * ((len(bytes.fromhex(expected)) - 4) // 2))

for stage, address, expected in [
    ('zq', 0x2b7e8, '00f020f9'),
    ('identity', 0x2b81c, 'fef77efc'),
    ('parameters', 0x2b874, 'fff7eafd'),
    ('clocks', 0x2b456, 'fff7e1ff'),
    ('timing', 0x2b472, 'fff75bbd'),
    ('training', 0x2b878, '054628b9'),
    ('ready', 0x2b934, 'e36dda00'),
]:
    payload = bytearray(inherited)
    # Bound the PLL lock poll, returning diagnostic state on failure.
    bound_polls()
    # Thumb-2 B.W to a nearby forward checkpoint (S=I1=I2=0, J1=J2=1).
    patch(address, expected, branch_to(address, 0x2d300))
    save(f'ddr-stage-{stage}.bin')
print('Prepared instrumented, preflight and inherited-clock DDR images; original retained.')
