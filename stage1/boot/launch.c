#include <stdint.h>
#define R32(a) (*(volatile uint32_t *)(a))
#define R8(a) (*(volatile uint8_t *)(a))

static void delay_ms(uint32_t ms)
{
    uint32_t lo, hi, start;
    __asm__ volatile("mrrc p15, 0, %0, %1, c14" : "=r"(start), "=r"(hi));
    do {
        __asm__ volatile("mrrc p15, 0, %0, %1, c14" : "=r"(lo), "=r"(hi));
    } while ((uint32_t)(lo - start) < ms * 24000u);
}

void prepare_hardware(void)
{
    R32(0x0003d000) = 0x424f4f54; /* BOOT milestone */
    /* Return to FEL on an early boot stall; /init disables it after USB
     * enumeration. Blank boot0 is required for this development-only recovery. */
    R32(0x020500b4) = 0x16aa0001;
    R32(0x020500b0) = 0x14af;
    R32(0x020500b8) = 0x16aa00b1;

    /* Disconnect FEL, silence MUSB IRQs, clear session; then hard-reset USB.
     * Bits/addresses match the awboot V853 CCU and upstream sunxi MUSB map.
     * Linux owns the subsequent deassert and PHY initialization.
     */
    R8(0x04100040) &= ~0x40u;
    R32(0x04100048) = 0;
    R8(0x04100050) = 0;
    R8(0x04100041) = 0;
    __asm__ volatile("dsb sy" ::: "memory");
    delay_ms(250);
    R32(0x02001a8c) &= ~((1u << 24) | (1u << 20) | (1u << 16));
    R32(0x02001a70) &= ~(1u << 30);
    __asm__ volatile("dsb sy" ::: "memory");
    delay_ms(10);
    R32(0x02001a8c) &= ~((1u << 8) | (1u << 4) | 1u);
    R32(0x02001a70) &= ~(1u << 31);
    R32(0x0003d000) = 0x4a554d50; /* JUMP milestone */
}
