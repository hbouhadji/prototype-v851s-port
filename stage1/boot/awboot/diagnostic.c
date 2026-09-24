// SPDX-License-Identifier: GPL-2.0+
#include <stdarg.h>
#include "main.h"
#include "dram.h"
#include "params.h"

static volatile uint32_t *const result = (void *)0x3d000;
static uint64_t ticks(void) {
    uint32_t lo,hi;
    __asm__ volatile("mrrc p15, 0, %0, %1, c14" : "=r"(lo), "=r"(hi));
    return ((uint64_t)hi<<32)|lo;
}
void sdelay(unsigned us) {
    uint64_t start=ticks();
    while (ticks()-start < (uint64_t)us*24) {}
}
int wait_register(unsigned addr,unsigned mask,unsigned expected,unsigned site) {
    uint64_t start=ticks();
    uint32_t value;
    do {
        value=read32(addr);
        if ((value&mask)==expected) return 1;
    } while (ticks()-start < 2400000);
    result[4]=addr; result[5]=value; result[6]=site;
    return 0;
}
static void character(char c) {
    unsigned n=result[1];
    if (n<0xe00) { ((volatile char *)0x3d100)[n]=c; result[1]=n+1; }
}
static void string(const char *s) { while (*s) character(*s++); }
static void number(unsigned n,unsigned base) {
    char buf[32]; unsigned i=0;
    do {buf[i++]="0123456789abcdef"[n%base];n/=base;} while(n);
    while(i) character(buf[--i]);
}
void debug(const char *fmt,...) {
    va_list ap; va_start(ap,fmt);
    while(*fmt) {
        if(*fmt!='%') { character(*fmt++); continue; }
        ++fmt;
        while(*fmt>='0' && *fmt<='9') ++fmt;
        switch(*fmt++) {
        case 's': string(va_arg(ap,const char *)); break;
        case 'd': case 'u': number(va_arg(ap,unsigned),10); break;
        case 'x': case 'X': number(va_arg(ap,unsigned),16); break;
        case 'c': character(va_arg(ap,int)); break;
        case '%': character('%'); break;
        default: character('?'); break;
        }
    }
    va_end(ap);
}
void awboot_entry(void) {
    // Use the original topology/timings; defer memory self-test to the host.
    static const uint32_t words[24]=STOCK_PARAMS;
    dram_para_t para;
    for(unsigned i=0;i<24;++i) ((uint32_t *)&para)[i]=words[i];
    para.dram_tpr13 &= ~BIT(28);
    for(unsigned i=0;i<8;++i) result[i]=0;
    result[0]=0x52554e31;
    result[2]=init_DRAM(0,&para);
    if(result[4]) result[2]=0x54494d45;
    result[0]=0x444f4e45;
}
