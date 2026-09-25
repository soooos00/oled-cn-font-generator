/**
 * @file    main.c  OLED font demo - pure ASCII source (safe for Keil AC5)
 */
#include "stm32f10x.h"
#include "delay.h"
#include "oled.h"
#include "oledfont.h"

int main(void) {
    SystemInit();
    delay_init();
    OLED_Init();

    /* page 0: name */
    OLED_ShowWord(0, 0, W_ZHOUKAIYUN);

    /* page 2: time + 12:34 */
    OLED_ShowWord(0, 2, W_SHIJIAN);
    OLED_ShowString(32, 2, ":12:34");

    /* page 4: motor normal running */
    OLED_ShowWord(0, 4, W_DIANJIZHENGCHANGYUNZUO);

    /* page 6: status + forward + 50% */
    OLED_ShowWord(0, 6, W_ZHUANGTAI);
    OLED_ShowString(32, 6, ":");
    OLED_ShowWord(40, 6, W_ZHENGZHUAN);
    OLED_ShowString(72, 6, " 50%");

    while (1) {
        /* motor logic: PWM output, speed measure, abnormal display ... */
    }
}
