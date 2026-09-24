#pragma once
#include <stdint.h>
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;
#define max(a,b) ((a)>(b)?(a):(b))
#define BIT(n) (1U << (n))
static inline uint32_t read32(uint32_t a) { return *(volatile uint32_t *)a; }
static inline void write32(uint32_t a,uint32_t v) { *(volatile uint32_t *)a=v; }
void sdelay(unsigned us);
