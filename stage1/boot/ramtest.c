#include <stdint.h>

/* Run from SRAM, no allocator or DRAM stack. Only peripheral write: watchdog
 * reload once per MiB, so a stalled memory transaction still resets to FEL. */
void ramtest(void)
{
    volatile uint32_t *r = (volatile uint32_t *)0x0003d000;
    r[0] = 0x52554e21; /* RUN! */
    r[1] = 0;
    r[2] = 0;
    r[3] = 0;
    r[4] = 0;
    uint32_t sctlr;
    __asm__ volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(sctlr));
    r[5] = sctlr;
    uint32_t cpsr;
    __asm__ volatile("mrs %0, cpsr" : "=r"(cpsr));
    r[6] = cpsr;
    if (sctlr & 5) { r[0] = 0x43414348; return; } /* no cached/MMU test */
    for (uint32_t pass = 0; pass < 2; pass++) {
        uint32_t mask = pass ? 0xa5a5a5a5 : 0x5a5a5a5a;
        r[1] = pass * 2 + 1;
        for (uint32_t a = 0x40000000; a < 0x48000000; a += 4) {
            if (!(a & 0xfffff)) *(volatile uint32_t *)0x020500b0 = 0x14af;
            *(volatile uint32_t *)a = a ^ mask;
        }
        __asm__ volatile("dsb sy" ::: "memory");
        r[1]++;
        for (uint32_t a = 0x40000000; a < 0x48000000; a += 4) {
            if (!(a & 0xfffff)) *(volatile uint32_t *)0x020500b0 = 0x14af;
            uint32_t got = *(volatile uint32_t *)a;
            if (got != (a ^ mask)) {
                r[2] = a;
                r[3] = a ^ mask;
                r[4] = got;
                r[0] = 0x4641494c; /* FAIL */
                return;
            }
        }
    }
    r[0] = 0x50415353; /* PASS */
}
