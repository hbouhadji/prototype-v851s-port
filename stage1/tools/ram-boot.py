#!/usr/bin/env python3
"""V85x RAM-only experiment. No flash, OTP, reset or arbitrary-address commands.

Run init-ddr, then test-ram, then boot. Power loss requires repeating them.
The full RAM test destroys volatile contents, never persistent storage.
"""
import argparse
import hashlib
import json
import os
import secrets
import struct
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'out'
LOG = BASE / 'logs'
XFEL = BASE / 'tools/xfel'
COOKIE_ADDR = 0x47fff000

def call(*args, timeout=45):
    env = dict(os.environ)
    env['XFEL_USB_TIMEOUT_MS'] = '120000' if timeout > 120 else '10000'
    p = subprocess.run([str(XFEL), *map(str, args)], capture_output=True, timeout=timeout, env=env)
    text = (p.stdout + p.stderr).decode(errors='replace').strip()
    with (LOG / 'fel-transcript.log').open('a') as f:
        f.write(f'{time.strftime("%Y-%m-%dT%H:%M:%S%z")} xfel {args!r}\n{text}\nexit={p.returncode}\n')
    if p.returncode:
        raise RuntimeError(f'xfel {args[0]}: {text}')
    return text

def version():
    text = call('version')
    if 'ID=0x00188600' not in text:
        raise RuntimeError(f'Unexpected SoC: {text}')
    print(text, flush=True)
    return text

def read(addr, size):
    file = LOG / 'fel-read.tmp'
    file.unlink(missing_ok=True)
    call('read', hex(addr), str(size), file)
    data = file.read_bytes()
    if len(data) != size:
        raise RuntimeError('Short FEL read')
    return data

def upload(addr, file, limit):
    data = file.read_bytes()
    if not 0 < len(data) <= limit:
        raise RuntimeError(f'Image exceeds assigned region: {file}')
    call('write', hex(addr), file)
    if read(addr, len(data)) != data:
        raise RuntimeError(f'FEL verification failed at {addr:#x}')
    print(f'Verified {file.name}: {len(data)} bytes at {addr:#010x}', flush=True)

def init_ddr():
    (LOG / 'ram-validated.json').unlink(missing_ok=True)
    upload(0x28000, OUT / 'ddr-stock.bin', 0x13000)
    print('Executing SRAM DDR initializer...', flush=True)
    call('exec', '0x28000')
    time.sleep(1)
    version()
    sparse_check()

def context():
    upload(0x28000, OUT / 'context.bin', 0x1000)
    call('exec', '0x28000')
    record = dict(zip(['magic', 'sp', 'lr', 'cpsr', 'sctlr', 'ttbr0', 'vbar',
                       'cntfrq', 'counter1_lo', 'counter1_hi', 'counter2_lo', 'counter2_hi'],
                      struct.unpack('<12I', read(0x3d000, 48))))
    (LOG / 'fel-context.json').write_text(json.dumps(record, indent=2) + '\n')
    print('FEL context:', {k: hex(v) for k, v in record.items()}, flush=True)
    if record['magic'] != 0x43545831:
        raise RuntimeError('SRAM context probe did not return a valid result')
    if record['sctlr'] & 5 or record['cpsr'] & 31 != 0x13:
        raise RuntimeError('Unexpected MMU/cache/CPU mode: review before DDR initialization')
    if not 0x20000 <= record['sp'] < 0x44000:
        raise RuntimeError('FEL stack outside expected SRAM: review before DDR initialization')
    if (record['counter1_lo'], record['counter1_hi']) == (record['counter2_lo'], record['counter2_hi']):
        raise RuntimeError('ARM physical counter is stopped: DDR delay loops would hang')
    return record

def preflight():
    context()
    clocks = {}
    for name, addr in [('pll_cpu', 0x02001000), ('pll_ddr', 0x02001010),
                       ('pll_periph', 0x02001020), ('cpu_axi', 0x02001500)]:
        clocks[name] = call('read32', hex(addr))
    (LOG / 'fel-clocks.json').write_text(json.dumps(clocks, indent=2) + '\n')
    print('Clock registers:', clocks, flush=True)
    diagnose_ddr(preflight_only=True)

def diagnose_ddr(preflight_only=False, inherited_clocks=False, stage=None, native=False):
    if native:
        raise RuntimeError('Native boot0 load at 0x20000 stalled FEL before execution. '
                           'Do not retry until its SRAM placement is corrected.')
    (LOG / 'ram-validated.json').unlink(missing_ok=True)
    if not preflight_only:
        context()
    name = ('ddr-native.bin' if native else 'ddr-preflight.bin' if preflight_only else
            f'ddr-stage-{stage}.bin' if stage else
            'ddr-inherited-clocks.bin' if inherited_clocks else 'ddr-instrumented.bin')
    upload(0x20000 if native else 0x28000, OUT / name, 0xb000 if native else 0x5000)
    upload(0x2d000, OUT / ('ddr-native-wrapper.bin' if native else 'ddr-diagnostic.bin'), 0xe000)
    if not preflight_only:
        watchdog_arm()
    print('Executing banner only...' if preflight_only else
          'Executing DDR with SRAM stack and captured character output...', flush=True)
    call('exec', '0x2d100')
    time.sleep(1)
    version()
    if not preflight_only:
        call('write32', '0x020500b8', '0x16aa0000')
    magic, length, size = struct.unpack('<3I', read(0x3d000, 12))
    if length > 0xe00:
        raise RuntimeError('Invalid diagnostic log length')
    output = read(0x3d100, length).decode(errors='replace') if length else ''
    prefix = Path(name).stem
    (LOG / f'{prefix}.log').write_text(output)
    (LOG / f'{prefix}-result.json').write_text(json.dumps(
        dict(magic=hex(magic), log_length=length, dram_mib=size), indent=2) + '\n')
    print(output, flush=True)
    if size == 0x54494d45:
        addr, value, site = struct.unpack('<3I', read(0x3d010, 12))
        (LOG / f'{prefix}-timeout.json').write_text(json.dumps(
            dict(address=hex(addr), value=hex(value), site=hex(site)), indent=2) + '\n')
        raise RuntimeError(f'Bounded DDR poll timed out: register={addr:#x}, value={value:#x}, site={site:#x}')
    if stage:
        if magic != 0x444f4e45 or size != 0x53544f50:
            raise RuntimeError(f'DDR checkpoint not reached: {stage}, magic={magic:#x}, result={size:#x}')
        r0 = struct.unpack('<I', read(0x3d01c, 4))[0]
        (LOG / f'{prefix}-result.json').write_text(json.dumps(
            dict(magic=hex(magic), return_value=hex(size), log_length=length,
                 checkpoint_r0=hex(r0), stage=stage), indent=2) + '\n')
        print(f'PASS: {stage} checkpoint reached; FEL returned, checkpoint r0={r0:#x}.', flush=True)
        return
    if preflight_only:
        if magic != 0x444f4e45 or size != 1 or not output:
            raise RuntimeError(f'Preflight did not pass: magic={magic:#x}, result={size}, log length={length}')
        print('PASS: banner captured and returned to FEL; no clock/DDR initialization.', flush=True)
        return
    if magic != 0x444f4e45 or size != 128:
        raise RuntimeError(f'DDR initialization not validated: magic={magic:#x}, size={size}')
    sparse_check()

def watchdog_arm():
    # D1/V85x watchdog register layout, also used by the FES image. If a DRAM
    # bus access stalls the CPU, reset after 16 s; blank boot0 permits FEL again.
    call('write32', '0x020500b4', '0x16aa0001')
    call('write32', '0x020500b0', '0x14af')
    call('write32', '0x020500b8', '0x16aa00b1')

def sparse_check():
    watchdog_arm()
    # Small independent regions before the full CPU test.
    addresses = [0x40010000, 0x44010000, 0x47ff0000]
    patterns = []
    for addr in addresses:
        data = secrets.token_bytes(4096)
        file = OUT / f'probe-{addr:x}.bin'
        file.write_bytes(data)
        upload(addr, file, 4096)
        patterns.append(data)
    for addr, data in zip(addresses, patterns):
        if read(addr, len(data)) != data:
            raise RuntimeError(f'RAM alias/retention failure at {addr:#x}')
    print('Sparse DDR check passed at 0, 64 and 127 MiB offsets.', flush=True)
    call('write32', '0x020500b8', '0x16aa0000')

def awboot_ddr():
    (LOG / 'ram-validated.json').unlink(missing_ok=True)
    context()
    upload(0x28000, OUT / 'ddr-awboot.bin', 0x13000)
    watchdog_arm()
    call('exec', '0x28000')
    version()
    call('write32', '0x020500b8', '0x16aa0000')
    values = struct.unpack('<8I', read(0x3d000, 32))
    magic, length, size = values[:3]
    if length > 0xe00:
        raise RuntimeError('Invalid awboot log length')
    output = read(0x3d100, length).decode(errors='replace') if length else ''
    (LOG / 'ddr-awboot.log').write_text(output)
    (LOG / 'ddr-awboot-result.json').write_text(json.dumps(dict(
        magic=hex(magic), size=size, timeout_address=hex(values[4]),
        timeout_value=hex(values[5]), timeout_line=values[6]), indent=2)+'\n')
    print(output, flush=True)
    if magic != 0x444f4e45 or size != 128:
        raise RuntimeError(f'awboot did not report 128 MiB: {values}')
    sparse_check()

def test_ram():
    (LOG / 'ram-validated.json').unlink(missing_ok=True)
    upload(0x28000, OUT / 'ramtest.bin', 0x13000)
    watchdog_arm()
    print('Testing all 128 MiB, two address-dependent patterns...', flush=True)
    call('exec', '0x28000', timeout=130)
    # FEL exec acknowledges before the CPU payload returns. The following
    # command must allow the complete uncached memory test to finish.
    call('write32', '0x020500b8', '0x16aa0000', timeout=130)
    result = struct.unpack('<7I', read(0x3d000, 28))
    record = dict(zip(['magic', 'phase', 'address', 'expected', 'actual', 'sctlr', 'cpsr'], result))
    (LOG / 'ram-test-result.json').write_text(json.dumps(record, indent=2) + '\n')
    if result[0] != 0x50415353 or result[1] != 4:
        raise RuntimeError(f'RAM test did not pass: {record}')
    if (record['cpsr'] & 31) != 0x13:
        raise RuntimeError('Unexpected CPU mode; review handoff before boot')
    cookie = secrets.token_bytes(32)
    (OUT / 'ram-cookie.bin').write_bytes(cookie)
    upload(COOKIE_ADDR, OUT / 'ram-cookie.bin', 32)
    record.update(cookie=cookie.hex(), time=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  bytes_tested=128*1024*1024, passes=2)
    (LOG / 'ram-validated.json').write_text(json.dumps(record, indent=2) + '\n')
    print('PASS: all 128 MiB verified twice; no data cache/MMU.', flush=True)

def boot():
    record = json.loads((LOG / 'ram-validated.json').read_text())
    watchdog_arm()
    if read(COOKIE_ADDR, 32) != bytes.fromhex(record['cookie']):
        raise RuntimeError('RAM test cookie lost: repeat DDR initialization and RAM test')
    call('write32', '0x020500b8', '0x16aa0000')
    image = OUT / 'linux/arch/arm/boot/Image'
    if not image.exists() or image.stat().st_size >= 0x1f00000:
        raise RuntimeError('Uncompressed kernel would overlap uploaded zImage')
    files = [(0x42000000, 'zImage', 0x1000000),
             (0x43000000, 'board.dtb', 0x100000),
             (0x44000000, 'initramfs.cpio.gz', 0x3f00000),
             (0x28000, 'launch.bin', 0x13000)]
    for addr, name, size in files:
        upload(addr, OUT / name, size)
    manifest = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                for _, name, _ in files}
    (LOG / 'last-boot-images.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Launching Linux. FEL USB should disconnect, then ACM should appear.', flush=True)
    try:
        call('exec', '0x28000')
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f'USB handoff result (not proof of Linux boot): {e}', flush=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['ddr-awboot', 'inspect', 'context', 'preflight', 'diagnose-ddr', 'ddr-native', 'ddr-inherited-clocks', 'ddr-stage-zq', 'ddr-stage-identity', 'ddr-stage-parameters', 'ddr-stage-clocks', 'ddr-stage-timing', 'ddr-stage-training', 'ddr-stage-ready', 'sparse-ram', 'init-ddr', 'test-ram', 'boot'])
args = parser.parse_args()
LOG.mkdir(exist_ok=True)
version()
if args.action != 'inspect':
    {'ddr-awboot': awboot_ddr, 'context': context, 'preflight': preflight, 'diagnose-ddr': diagnose_ddr,
     'ddr-inherited-clocks': lambda: diagnose_ddr(inherited_clocks=True),
     'ddr-native': lambda: diagnose_ddr(native=True),
     'ddr-stage-zq': lambda: diagnose_ddr(stage='zq'),
     'ddr-stage-identity': lambda: diagnose_ddr(stage='identity'),
     'ddr-stage-parameters': lambda: diagnose_ddr(stage='parameters'),
     'ddr-stage-clocks': lambda: diagnose_ddr(stage='clocks'),
     'ddr-stage-timing': lambda: diagnose_ddr(stage='timing'),
     'ddr-stage-training': lambda: diagnose_ddr(stage='training'),
     'ddr-stage-ready': lambda: diagnose_ddr(stage='ready'),
     'sparse-ram': sparse_check,
     'init-ddr': init_ddr, 'test-ram': test_ram, 'boot': boot}[args.action]()
