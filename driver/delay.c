/**
 * @file    delay.c  Busy-wait delay by polling SysTick.
 *                   NO interrupt, NO SysTick_Handler -> no clash with stm32f10x_it.c
 */
#include "delay.h"

void delay_init(void) {
    /* Nothing to configure: SysTick is set up per call.
       Intentionally does NOT define SysTick_Handler. */
    SysTick->CTRL &= ~(SysTick_CTRL_ENABLE_Msk | SysTick_CTRL_TICKINT_Msk);
}

/** Blocking wait with SysTick in polling mode (CTRL.TICKINT = 0) */
static void systick_wait(uint32_t ticks) {
    if (ticks == 0) return;
    if (ticks > 0x00FFFFFF) ticks = 0x00FFFFFF;   /* 24-bit reload limit */
    SysTick->LOAD = ticks - 1;
    SysTick->VAL  = 0;
    SysTick->CTRL = SysTick_CTRL_ENABLE_Msk | SysTick_CTRL_CLKSOURCE_Msk;
    while (!(SysTick->CTRL & SysTick_CTRL_COUNTFLAG_Msk));
    SysTick->CTRL &= ~SysTick_CTRL_ENABLE_Msk;
}

void delay_us(uint16_t us) {
    systick_wait((uint32_t)us * (SystemCoreClock / 1000000));
}

void delay_ms(uint16_t ms) {
    while (ms--) systick_wait(SystemCoreClock / 1000);
}
