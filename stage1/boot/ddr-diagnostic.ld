OUTPUT_ARCH(arm)
ENTRY(_start)
SECTIONS {
    . = 0x0002d000;
    .logger : { *(.text.logger) }
    ASSERT(. <= 0x0002d100, "Logger overlaps entry")
    . = 0x0002d100;
    .text : { *(.text.entry) }
    ASSERT(. <= 0x0002d300, "Entry overlaps checkpoint")
    . = 0x0002d300;
    .checkpoint : { *(.text.checkpoint) }
    ASSERT(. <= 0x0002d400, "Checkpoint overlaps PLL wait")
    . = 0x0002d400;
    .pll_wait : { *(.text.pll_wait) }
    ASSERT(. <= 0x0002d500, "PLL wait overlaps PHY waits")
    . = 0x0002d500;
    .phy_wait : { *(.text.phy_wait) }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
    ASSERT(. < 0x0003b000, "Diagnostic overlaps SRAM stack")
}
