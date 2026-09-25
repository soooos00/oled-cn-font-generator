/**
 * @file    oled.h
 * @brief   SSD1306 128x64 OLED driver with GRAM buffer (software I2C / STM32 SPL)
 * @note    Default pins: PB8=SCL, PB9=SDA. Change macros in oled.c to remap.
 *
 *          All drawing goes into a 1KB RAM buffer first. Call OLED_Refresh()
 *          (or OLED_RefreshPage) to push it to the panel. This avoids flicker
 *          when only part of the screen changes.
 */
#ifndef __OLED_H__
#define __OLED_H__

#include "stm32f10x.h"

#define OLED_CMD    0x00
#define OLED_DATA   0x40

#define OLED_WIDTH  128
#define OLED_HEIGHT 64
#define OLED_PAGES  8

/* ---- init / power ---- */
void OLED_Init(void);
void OLED_On(void);
void OLED_Off(void);

/* ---- buffer -> panel ---- */
void OLED_Refresh(void);                          /* whole buffer, 1 burst per page */
void OLED_RefreshDirty(void);                     /* ONLY pages that changed        */
void OLED_RefreshPage(uint8_t page);              /* one page (0~7)                 */
void OLED_RefreshPages(uint8_t y0, uint8_t y1);   /* page range y0..y1              */
void OLED_RefreshArea(uint8_t x, uint8_t y, uint8_t w, uint8_t h);  /* pixel area  */

/* NOTE: a 16px-tall glyph spans TWO pages. If you refresh manually,
 *       remember page y AND y+1. OLED_RefreshDirty() handles this for you. */

/* ---- buffer ops ---- */
void OLED_Clear(void);                            /* clear buffer + panel */
void OLED_BufClear(void);                         /* clear buffer only    */
void OLED_DrawPoint(uint8_t x, uint8_t y, uint8_t on);
void OLED_DrawHLine(uint8_t x, uint8_t y, uint8_t w);
void OLED_BufMat(uint8_t x, uint8_t page, const uint8_t *m, uint8_t w);

/* ---- low level ---- */
void OLED_SetPos(uint8_t x, uint8_t y);
void OLED_WR_Byte(uint8_t data, uint8_t cmd);

#endif
