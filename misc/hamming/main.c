#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#define CODE_BITS 16
#define DATA_BITS 11

static const uint8_t hamming_pos[4] = {1, 2, 4, 8};

static const uint8_t data_pos[DATA_BITS] = {3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15};

// syndrome 把所有为 1 的比特异或
static uint16_t syndrome(uint16_t code) {
        uint16_t s = 0;
        for (int bit = 0; bit < CODE_BITS; bit++) {
                if (code & (1u << bit)) {
                        s ^= (uint16_t)bit;
                }
        }
        return s;
}

// odd_parity 判断码字中置位数是否为奇数
static int odd_parity(uint16_t code) {
        int p = 0;
        while (code) {
                p ^= 1;
                code &= (uint16_t)(code - 1);
        }
        return p;
}

// encode 输入 data 为低 11 位，返回 16 位 ECC 码字
uint16_t encode(uint16_t data) {
        uint16_t code = 0;

        // 放入数据
        for (int i = 0; i < DATA_BITS; i++) {
                if (data & (1u << i)) {
                        code |= (uint16_t)(1u << data_pos[i]);
                }
        }

        // 计算 syndrome
        uint16_t s = syndrome(code);

        // 设置 4 个校验位
        for (int j = 0; j < 4; j++) {
                if (s & (1u << j)) {
                        code |= (uint16_t)(1u << hamming_pos[j]);
                }
        }

        // 设置总偶校验位
        if (odd_parity(code)) {
                code |= 1u;
        }

        return code;
}

// decode
// 译码（0:无错误，1:纠正了1位错误，-1:参数错误，-2:检测到2位错误，无法纠正）
int decode(uint16_t* code, uint16_t* data) {
        if (!code || !data) {
                return -1;
        }

        uint16_t s      = syndrome(*code);
        int      p      = odd_parity(*code);
        int      result = 0;

        if (s == 0 && p == 0) {
                // nothing
        } else if (s == 0 && p == 1) {
                // 总校验位出错，但不影响数据
                *code ^= 1u;
                result = 1;
        } else if (s != 0 && p != 0) {
                // 1 位错误，s 就是错误编号
                *code ^= (uint16_t)(1u << s);
                result = 1;
        } else {
                // 2 位错误，不可纠正
                return -2;
        }

        // 取出数据
        uint16_t out = 0;
        for (int i = 0; i < DATA_BITS; i++) {
                if (*code & (1u << data_pos[i])) {
                        out |= (uint16_t)(1u << i);
                }
        }

        *data = out;

        return result;
}

int main(void) {
        uint16_t data = 0X55;
        uint16_t code = encode(data);

        printf("encoded = 0X%04x\n", code);

        // 模拟出错
        // code ^= (1u << 5);
        // code ^= (1u << 7);

        uint16_t recovered;
        int      ret = decode(&code, &recovered);

        printf("decode return = %d\n", ret);
        printf("recovered     = 0X%03x\n", recovered);

        return 0;
}
