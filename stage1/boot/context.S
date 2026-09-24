.syntax unified
.cpu cortex-a7
.arm
.section .text.entry, "ax"
.global _start
_start:
    push {r0-r3, lr}
    ldr r0, =0x0003d000
    ldr r1, =0x43545831
    str r1, [r0]
    add r1, sp, #20
    str r1, [r0, #4]
    str lr, [r0, #8]
    mrs r1, cpsr
    str r1, [r0, #12]
    mrc p15, 0, r1, c1, c0, 0
    str r1, [r0, #16]
    mrc p15, 0, r1, c2, c0, 0
    str r1, [r0, #20]
    mrc p15, 0, r1, c12, c0, 0
    str r1, [r0, #24]
    mrc p15, 0, r1, c14, c0, 0
    str r1, [r0, #28]
    isb
    mrrc p15, 0, r1, r2, c14
    str r1, [r0, #32]
    str r2, [r0, #36]
    mov r3, #1024
1:  subs r3, #1
    bne 1b
    isb
    mrrc p15, 0, r1, r2, c14
    str r1, [r0, #40]
    str r2, [r0, #44]
    dsb sy
    pop {r0-r3, pc}
