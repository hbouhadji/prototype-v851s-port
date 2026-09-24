#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -mfloat-abi=soft -Os \
    -ffreestanding -fno-builtin -nostdlib -Wl,--build-id=none \
    -T boot/sram.ld boot/ramtest.S boot/ramtest.c -o out/ramtest.elf
arm-none-eabi-objcopy -O binary out/ramtest.elf out/ramtest.bin
arm-none-eabi-size out/ramtest.elf
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -mfloat-abi=soft -Os \
    -ffreestanding -fno-builtin -nostdlib -Wl,--build-id=none \
    -T boot/sram.ld boot/launch.S boot/launch.c -o out/launch.elf
arm-none-eabi-objcopy -O binary out/launch.elf out/launch.bin
arm-none-eabi-size out/launch.elf
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -nostdlib -Wl,--build-id=none \
    -T boot/sram.ld boot/context.S -o out/context.elf
arm-none-eabi-objcopy -O binary out/context.elf out/context.bin
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -nostdlib -Wl,--build-id=none \
    -T boot/ddr-diagnostic.ld boot/ddr-diagnostic.S -o out/ddr-diagnostic.elf
arm-none-eabi-objcopy -O binary out/ddr-diagnostic.elf out/ddr-diagnostic.bin
arm-none-eabi-gcc -mcpu=cortex-a7 -marm -nostdlib -Wl,--build-id=none -DSTOCK_DDR \
    -T boot/ddr-diagnostic.ld boot/ddr-diagnostic.S -o out/ddr-native-wrapper.elf
arm-none-eabi-objcopy -O binary out/ddr-native-wrapper.elf out/ddr-native-wrapper.bin
