#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -mfloat-abi=soft -Os \
  -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -nostdlib \
  -Wl,--build-id=none,--gc-sections -T boot/sram.ld \
  boot/awboot/entry.S boot/awboot/diagnostic.c boot/awboot/dram.c \
  -lgcc -o out/ddr-awboot.elf
arm-none-eabi-objcopy -O binary out/ddr-awboot.elf out/ddr-awboot.bin
arm-none-eabi-size out/ddr-awboot.elf
