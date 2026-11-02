// Yaz0 decompressor: yaz0dec <in> <out>
// Header: "Yaz0", u32 BE decompressed size, u32 BE alignment, u32 pad; then code/data stream.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: yaz0dec in out\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 1; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *src = malloc(n);
    if (!src || fread(src, 1, n, f) != (size_t)n) { fclose(f); return 1; }
    fclose(f);
    if (n < 16 || src[0] != 'Y' || src[1] != 'a' || src[2] != 'z' || src[3] != '0') {
        fprintf(stderr, "not Yaz0\n"); return 1;
    }
    uint32_t size = (uint32_t)src[4] << 24 | src[5] << 16 | src[6] << 8 | src[7];
    uint8_t *dst = malloc(size);
    long sp = 16; uint32_t dp = 0;
    while (dp < size && sp < n) {
        uint8_t code = src[sp++];
        for (int b = 0; b < 8 && dp < size; b++, code <<= 1) {
            if (code & 0x80) {
                if (sp >= n) break;
                dst[dp++] = src[sp++];
            } else {
                if (sp + 1 >= n) break;
                uint8_t b1 = src[sp++], b2 = src[sp++];
                uint32_t dist = ((b1 & 0x0F) << 8 | b2) + 1;
                uint32_t len = b1 >> 4;
                if (len == 0) { len = src[sp++] + 0x12; } else { len += 2; }
                if (dist > dp) { fprintf(stderr, "bad backref\n"); return 1; }
                for (uint32_t i = 0; i < len && dp < size; i++, dp++) dst[dp] = dst[dp - dist];
            }
        }
    }
    FILE *o = fopen(argv[2], "wb");
    if (!o) { perror("out"); return 1; }
    fwrite(dst, 1, size, o);
    fclose(o);
    return dp == size ? 0 : 1;
}
