OUTPUT_ARCH(arm)
ENTRY(_start)
SECTIONS {
    . = 0x00028000;
    .text : { *(.text.entry) *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
    ASSERT(. < 0x0003b000, "SRAM payload exceeds reserved code area")
}
