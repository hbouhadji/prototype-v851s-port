.syntax unified
.cpu cortex-a7
.arm
.section .text.entry, "ax"
.global _start
_start:
    push {r0-r12, lr}
    ldr r0, =saved_sp
    str sp, [r0]
    mrs r1, cpsr
    ldr r0, =saved_cpsr
    str r1, [r0]
    cpsid if
    ldr sp, =0x0003c000
    mov r0, #0
    mcr p15, 0, r0, c7, c5, 0
    dsb sy
    isb
    bl awboot_entry
    dsb sy
    ldr r0, =saved_sp
    ldr sp, [r0]
    ldr r0, =saved_cpsr
    ldr r1, [r0]
    msr cpsr_c, r1
    pop {r0-r12, pc}
.align 2
saved_sp: .word 0
saved_cpsr: .word 0
