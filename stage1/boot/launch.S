/* ARMv7 handoff following Linux Documentation/arch/arm/booting.rst.
 * SRAM layout and V85x registers are based on szemzoa/awboot mach-v851s.
 * No DRAM initialization here: FEL has already uploaded and verified images.
 */
.syntax unified
.cpu cortex-a7
.arm
.section .text.entry, "ax"
.global _start
_start:
    cpsid if
    ldr sp, =0x0003c000
    bl clean_caches
    mrc p15, 0, r0, c1, c0, 0
    bic r0, r0, #1
    bic r0, r0, #4
    bic r0, r0, #0x1000
    mcr p15, 0, r0, c1, c0, 0
    dsb sy
    isb
    mov r0, #0
    mcr p15, 0, r0, c8, c7, 0
    mcr p15, 0, r0, c7, c5, 0
    mcr p15, 0, r0, c7, c5, 6
    dsb sy
    isb
    ldr r0, =24000000
    mcr p15, 0, r0, c14, c0, 0
    bl prepare_hardware
    dsb sy
    isb
    mov r0, #0
    mvn r1, #0
    ldr r2, =0x43000000
    ldr r3, =0x42000000
    bx r3

/* Clean/invalidate every data/unified cache level using CCSIDR geometry. */
clean_caches:
    dsb sy
    mrc p15, 1, r0, c0, c0, 1
    ubfx r3, r0, #24, #3
    lsl r3, r3, #1
    mov r10, #0
1:
    cmp r10, r3
    bge 5f
    add r2, r10, r10, lsr #1
    lsr r1, r0, r2
    and r1, r1, #7
    cmp r1, #2
    blt 4f
    mcr p15, 2, r10, c0, c0, 0
    isb
    mrc p15, 1, r1, c0, c0, 0
    and r2, r1, #7
    add r2, r2, #4
    ubfx r4, r1, #3, #10
    clz r5, r4
    ubfx r7, r1, #13, #15
2:
    mov r9, r4
3:
    orr r11, r10, r9, lsl r5
    orr r11, r11, r7, lsl r2
    mcr p15, 0, r11, c7, c14, 2
    subs r9, r9, #1
    bge 3b
    subs r7, r7, #1
    bge 2b
4:
    add r10, r10, #2
    b 1b
5:
    mov r0, #0
    mcr p15, 2, r0, c0, c0, 0
    dsb sy
    isb
    bx lr
