/**
 * @file    oled.c  SSD1306 software I2C driver with GRAM buffer (STM32 SPL)
 *
 * Why a buffer:
 *   Drawing straight to the panel means every glyph column is its own I2C
 *   transaction (16 per Chinese char). When a value changes you must erase
 *   then redraw, which flickers.
 *   With a buffer, drawing is pure RAM work, and one OLED_RefreshPage() pushes
 *   a whole page (128 bytes) in a SINGLE I2C transaction.
 *
 *   Cost: 1024 bytes RAM (128 x 64 / 8). C8T6 has 20KB, so this is fine.
 */
#include "oled.h"
#include <string.h>

#define OLED_GPIO_PORT   GPIOB
#define OLED_GPIO_CLK    RCC_APB2Periph_GPIOB
#define OLED_SCL_PIN     GPIO_Pin_8
#define OLED_SDA_PIN     GPIO_Pin_9

#define OLED_ADDR        0x78          /* SSD1306 I2C addr (0x3C << 1); try 0x7A if blank */

#define OLED_SCL_H()     GPIO_SetBits(OLED_GPIO_PORT, OLED_SCL_PIN)
#define OLED_SCL_L()     GPIO_ResetBits(OLED_GPIO_PORT, OLED_SCL_PIN)
#define OLED_SDA_H()     GPIO_SetBits(OLED_GPIO_PORT, OLED_SDA_PIN)
#define OLED_SDA_L()     GPIO_ResetBits(OLED_GPIO_PORT, OLED_SDA_PIN)
#define OLED_SDA_READ()  GPIO_ReadInputDataBit(OLED_GPIO_PORT, OLED_SDA_PIN)

/* ---------------- GRAM buffer (1KB) + dirty page tracking ---------------- */
static uint8_t OLED_GRAM[OLED_PAGES][OLED_WIDTH];
static uint8_t OLED_Dirty[OLED_PAGES];      /* 1 = this page changed since last push */

static void OLED_MarkDirty(uint8_t page) {
    if (page < OLED_PAGES) OLED_Dirty[page] = 1;
}

/* ---------------- software I2C ---------------- */
static void Delay_Us(uint16_t us) {
    for (uint32_t i = 0; i < (uint32_t)us * 8; i++) __NOP();
}

static void I2C_Start(void) {
    OLED_SDA_H(); OLED_SCL_H(); Delay_Us(2);
    OLED_SDA_L(); Delay_Us(2);
    OLED_SCL_L();
}

static void I2C_Stop(void) {
    OLED_SDA_L(); OLED_SCL_H(); Delay_Us(2);
    OLED_SDA_H(); Delay_Us(2);
}

static void I2C_WaitAck(void) {
    uint16_t t = 0;
    OLED_SDA_H(); Delay_Us(1);
    OLED_SCL_H(); Delay_Us(1);
    while (OLED_SDA_READ() && (++t < 5000));   /* timeout: never hang forever */
    OLED_SCL_L(); Delay_Us(1);
}

static void I2C_SendByte(uint8_t b) {
    for (uint8_t i = 0; i < 8; i++) {
        OLED_SCL_L();
        if (b & 0x80) OLED_SDA_H(); else OLED_SDA_L();
        Delay_Us(1);
        OLED_SCL_H(); Delay_Us(1);
        b <<= 1;
    }
    OLED_SCL_L();
}

void OLED_WR_Byte(uint8_t data, uint8_t cmd) {
    I2C_Start();
    I2C_SendByte(OLED_ADDR); I2C_WaitAck();
    I2C_SendByte(cmd);       I2C_WaitAck();
    I2C_SendByte(data);      I2C_WaitAck();
    I2C_Stop();
}

void OLED_SetPos(uint8_t x, uint8_t y) {
    OLED_WR_Byte(0xB0 | y, OLED_CMD);                    /* page 0xB0~0xB7 */
    OLED_WR_Byte(0x10 | ((x >> 4) & 0x0F), OLED_CMD);    /* column high nibble */
    OLED_WR_Byte(0x00 | (x & 0x0F), OLED_CMD);           /* column low nibble  */
}

/** Burst-write w bytes of one page starting at column x (single I2C transaction) */
static void OLED_BurstPage(uint8_t page, uint8_t x, uint8_t w) {
    if (page >= OLED_PAGES || x >= OLED_WIDTH) return;
    if ((uint16_t)x + w > OLED_WIDTH) w = OLED_WIDTH - x;
    OLED_SetPos(x, page);
    I2C_Start();
    I2C_SendByte(OLED_ADDR);  I2C_WaitAck();
    I2C_SendByte(OLED_DATA);  I2C_WaitAck();      /* 0x40 = data stream follows */
    for (uint8_t i = 0; i < w; i++) {
        I2C_SendByte(OLED_GRAM[page][x + i]);
        I2C_WaitAck();
    }
    I2C_Stop();
}

/* ---------------- buffer -> panel ---------------- */
void OLED_Refresh(void) {
    for (uint8_t p = 0; p < OLED_PAGES; p++) OLED_BurstPage(p, 0, OLED_WIDTH);
    memset(OLED_Dirty, 0, sizeof(OLED_Dirty));
}

/** Push ONLY the pages that were drawn into since the last refresh.
 *  This is the one to call in your main loop - no need to work out
 *  which pages your text occupies. */
void OLED_RefreshDirty(void) {
    for (uint8_t p = 0; p < OLED_PAGES; p++) {
        if (OLED_Dirty[p]) {
            OLED_BurstPage(p, 0, OLED_WIDTH);
            OLED_Dirty[p] = 0;
        }
    }
}

void OLED_RefreshPage(uint8_t page) {
    OLED_BurstPage(page, 0, OLED_WIDTH);
    if (page < OLED_PAGES) OLED_Dirty[page] = 0;
}

void OLED_RefreshPages(uint8_t y0, uint8_t y1) {
    if (y0 > y1) { uint8_t t = y0; y0 = y1; y1 = t; }
    if (y1 >= OLED_PAGES) y1 = OLED_PAGES - 1;
    for (uint8_t p = y0; p <= y1; p++) {
        OLED_BurstPage(p, 0, OLED_WIDTH);
        OLED_Dirty[p] = 0;
    }
}

void OLED_RefreshArea(uint8_t x, uint8_t y, uint8_t w, uint8_t h) {
    if (h == 0 || w == 0 || x >= OLED_WIDTH || y >= OLED_HEIGHT) return;
    uint8_t p0 = y >> 3;
    uint8_t p1 = (uint8_t)((y + h - 1) >> 3);
    if (p1 >= OLED_PAGES) p1 = OLED_PAGES - 1;
    for (uint8_t p = p0; p <= p1; p++) OLED_BurstPage(p, x, w);
}

/* ---------------- buffer ops ---------------- */
void OLED_BufClear(void) {
    memset(OLED_GRAM, 0, sizeof(OLED_GRAM));
    memset(OLED_Dirty, 1, sizeof(OLED_Dirty));   /* everything needs a repaint */
}

void OLED_Clear(void) {
    OLED_BufClear();
    OLED_Refresh();
}

void OLED_DrawPoint(uint8_t x, uint8_t y, uint8_t on) {
    if (x >= OLED_WIDTH || y >= OLED_HEIGHT) return;
    if (on) OLED_GRAM[y >> 3][x] |=  (uint8_t)(1 << (y & 7));
    else    OLED_GRAM[y >> 3][x] &= (uint8_t)~(1 << (y & 7));
    OLED_MarkDirty(y >> 3);
}

void OLED_DrawHLine(uint8_t x, uint8_t y, uint8_t w) {
    for (uint8_t i = 0; i < w; i++) OLED_DrawPoint(x + i, y, 1);
}

/** Write a glyph bitmap (column-major, upper 8 rows then lower 8) into buffer.
 *  Uses '=' so redrawing a char cleanly erases the previous one. */
void OLED_BufMat(uint8_t x, uint8_t page, const uint8_t *m, uint8_t w) {
    if (page >= OLED_PAGES) return;
    for (uint8_t col = 0; col < w; col++) {
        if ((uint16_t)x + col >= OLED_WIDTH) break;
        OLED_GRAM[page][x + col] = m[col];
        OLED_MarkDirty(page);
        if (page + 1 < OLED_PAGES) {
            OLED_GRAM[page + 1][x + col] = m[w + col];
            OLED_MarkDirty(page + 1);
        }
    }
}

/* ---------------- init ---------------- */
void OLED_On(void)  { OLED_WR_Byte(0x8D, OLED_CMD); OLED_WR_Byte(0x14, OLED_CMD); OLED_WR_Byte(0xAF, OLED_CMD); }
void OLED_Off(void) { OLED_WR_Byte(0x8D, OLED_CMD); OLED_WR_Byte(0x10, OLED_CMD); OLED_WR_Byte(0xAE, OLED_CMD); }

void OLED_Init(void) {
    GPIO_InitTypeDef g;
    RCC_APB2PeriphClockCmd(OLED_GPIO_CLK | RCC_APB2Periph_AFIO, ENABLE);
    g.GPIO_Pin   = OLED_SCL_PIN | OLED_SDA_PIN;
    g.GPIO_Mode  = GPIO_Mode_Out_OD;
    g.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(OLED_GPIO_PORT, &g);

    Delay_Us(60000);
    OLED_WR_Byte(0xAE, OLED_CMD);
    OLED_WR_Byte(0x00, OLED_CMD);
    OLED_WR_Byte(0x10, OLED_CMD);
    OLED_WR_Byte(0x40, OLED_CMD);
    OLED_WR_Byte(0xB0, OLED_CMD);
    OLED_WR_Byte(0x81, OLED_CMD); OLED_WR_Byte(0xCF, OLED_CMD);
    OLED_WR_Byte(0xA1, OLED_CMD);          /* 0xA0 = mirrored horizontally */
    OLED_WR_Byte(0xA6, OLED_CMD);
    OLED_WR_Byte(0xA8, OLED_CMD); OLED_WR_Byte(0x3F, OLED_CMD);
    OLED_WR_Byte(0xC8, OLED_CMD);          /* 0xC0 = flipped vertically */
    OLED_WR_Byte(0xD3, OLED_CMD); OLED_WR_Byte(0x00, OLED_CMD);
    OLED_WR_Byte(0xD5, OLED_CMD); OLED_WR_Byte(0x80, OLED_CMD);
    OLED_WR_Byte(0xD9, OLED_CMD); OLED_WR_Byte(0xF1, OLED_CMD);
    OLED_WR_Byte(0xDA, OLED_CMD); OLED_WR_Byte(0x12, OLED_CMD);
    OLED_WR_Byte(0xDB, OLED_CMD); OLED_WR_Byte(0x40, OLED_CMD);
    OLED_WR_Byte(0x8D, OLED_CMD); OLED_WR_Byte(0x14, OLED_CMD);
    OLED_WR_Byte(0xAF, OLED_CMD);
    OLED_Clear();
}
