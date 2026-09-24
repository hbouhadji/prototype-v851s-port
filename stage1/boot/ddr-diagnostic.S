.syntax unified
.cpu cortex-a7
.section .text.logger, "ax"
.thumb
.global log_character
.thumb_func
log_character:
    push {r1-r3, lr}
    ldr r1, =0x0003d004
    ldr r2, [r1]
    cmp r2, #0xe00
    bhs 1f
    ldr r3, =0x0003d100
    strb r0, [r3, r2]
    adds r2, #1
    str r2, [r1]
1:  pop {r1-r3, pc}
    .ltorg

.section .text.entry, "ax"
.arm
.global _start
_start:
    ldr r0, =saved_registers
    stmia r0, {r4-r12, sp, lr}
    mrs r1, cpsr
    str r1, [r0, #44]
    mrc p15, 0, r1, c1, c0, 0
    str r1, [r0, #48]
    cpsid if
    ldr sp, =0x0003c000
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0
    mcr p15, 0, r0, c7, c5, 6
    dsb sy
    isb
    ldr r1, =0x0003d000
    str r0, [r1, #4]
    str r0, [r1, #8]
    ldr r0, =0x52554e31
    str r0, [r1]
#ifdef STOCK_DDR
    /* Only clear the stock BSS and call init_DRAM. Never enter boot0 main. */
    ldr r0, =0x00020408
    blx r0
    ldr r1, =0x0002aa00
    mov r0, #1
    strb r0, [r1]
    mov r0, #0
    ldr r1, =0x00020038
    ldr r3, =0x00024cbd
    blx r3
#else
    ldr r0, =0x00028000
    blx r0
#endif
.global diagnostic_done
diagnostic_done:
    ldr r1, =0x0003d000
    str r0, [r1, #8]
    ldr r0, =0x444f4e45
    str r0, [r1]
    dsb sy
    ldr r0, =saved_registers
    ldr r1, [r0, #48]
    mcr p15, 0, r1, c1, c0, 0
    isb
    ldr r1, [r0, #44]
    ldmia r0, {r4-r12, sp, lr}
    msr cpsr_c, r1
    bx lr
    .ltorg
saved_registers: .space 52

/* A diagnostic cut point abandons the FES stack and uses the same return
 * path as a completed FES call. Only used before DRAM controller setup. */
.section .text.checkpoint, "ax"
.thumb
.thumb_func
.global diagnostic_checkpoint
diagnostic_checkpoint:
    ldr r1, =0x0003d01c
    str r0, [r1]
    ldr r0, =0x53544f50
    ldr sp, =0x0003c000
    ldr r1, =diagnostic_done
    bx r1
    .ltorg

.section .text.phy_wait, "ax"
.thumb
.macro phy_wait address, mask, expected, resume, site
    .balign 128
    push {r0-r12, lr}
    ldr r0, =\address
    ldr r1, =1000000
1:  ldr r3, [r0]
    and r2, r3, #\mask
    cmp r2, #\expected
    beq 2f
    subs r1, #1
    bne 1b
    ldr r1, =0x0003d010
    str r0, [r1]
    str r3, [r1, #4]
    ldr r0, =\site
    str r0, [r1, #8]
    ldr r0, =0x54494d45
    ldr sp, =0x0003c000
    ldr r1, =diagnostic_done
    bx r1
2:  pop {r0-r12, lr}
    ldr pc, =(\resume + 1)
    .ltorg
.endm
phy_wait 0x03103010, 1, 1, 0x2b0be, 0x2b0b6
phy_wait 0x03103010, 1, 1, 0x2b0ea, 0x2b0e2
phy_wait 0x03103018, 7, 3, 0x2b11c, 0x2b112
phy_wait 0x03103018, 7, 1, 0x2b140, 0x2b134
phy_wait 0x03103010, 1, 1, 0x2b174, 0x2b16c
phy_wait 0x03103018, 1, 1, 0x2b236, 0x2b230

.section .text.pll_wait, "ax"
.thumb
.thumb_func
.global diagnostic_pll_wait
diagnostic_pll_wait:
    ldr r0, =1000000
1:  ldr r3, [r4]
    tst r3, #0x10000000
    bne 2f
    subs r0, #1
    bne 1b
    ldr r1, =0x0003d010
    str r4, [r1]
    str r3, [r1, #4]
    ldr r0, =0x54494d45
    ldr sp, =0x0003c000
    ldr r1, =diagnostic_done
    bx r1
2:  ldr r0, =0x0002abb7
    bx r0
    .ltorg
