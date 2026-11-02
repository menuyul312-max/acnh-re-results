// Batch Tegra X1 texture decoder.
// stdin, one job per line:
//   <blob> <offset> <size> <format> <width> <height> <blk_height_log2> <sw_r> <sw_g> <sw_b> <sw_a> <out>
// format = BNTX surface format (type << 8 | variant). Writes RGBA8 PNG (or
// Radiance .hdr for BC6H). Channel swizzle sources: 0=0 1=1 2=R 3=G 4=B 5=A.
// Prints "OK <out>" or "ERR <reason> <out>" per job.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#define BCDEC_BC4BC5_PRECISE
#define BCDEC_IMPLEMENTATION
#include "bcdec.h"
#include "astc.h"

static uint32_t div_up(uint32_t n, uint32_t d) { return (n + d - 1) / d; }

static size_t gob_addr(uint32_t x, uint32_t y, uint32_t width_bytes, uint32_t bh) {
    uint32_t wg = div_up(width_bytes, 64);
    size_t a = (size_t)(y / (8 * bh)) * 512 * bh * wg + (x / 64) * 512 * bh + ((y % (8 * bh)) / 8) * 512;
    return a + ((x % 64) / 32) * 256 + ((y % 8) / 2) * 64 + ((x % 32) / 16) * 32 + (y % 2) * 16 + (x % 16);
}

static int deswizzle(const uint8_t *src, size_t srclen, uint8_t *dst, uint32_t wb, uint32_t hb, uint32_t bpp, uint32_t bh) {
    for (uint32_t y = 0; y < hb; y++)
        for (uint32_t x = 0; x < wb; x++) {
            size_t s = gob_addr(x * bpp, y, wb * bpp, bh);
            if (s + bpp > srclen) return 0;
            memcpy(dst + ((size_t)y * wb + x) * bpp, src + s, bpp);
        }
    return 1;
}

typedef struct { int bw, bh, bpp; } fmtinfo;

static int fmt_info(int type, fmtinfo *f) {
    static const int astc[][2] = {{4,4},{5,4},{5,5},{6,5},{6,6},{8,5},{8,6},{8,8},{10,5},{10,6},{10,8},{10,10},{12,10},{12,12}};
    f->bw = f->bh = 1;
    switch (type) {
    case 0x02: f->bpp = 1; return 1;                  // R8
    case 0x07: case 0x09: f->bpp = 2; return 1;       // R5G6B5, R8G8
    case 0x0b: case 0x0c: case 0x0e: f->bpp = 4; return 1; // RGBA8, BGRA8, RGB10A2
    case 0x1a: case 0x1d: f->bw = f->bh = 4; f->bpp = 8; return 1;
    case 0x1b: case 0x1c: case 0x1e: case 0x1f: case 0x20: f->bw = f->bh = 4; f->bpp = 16; return 1;
    }
    if (type >= 0x2d && type <= 0x3a) { f->bw = astc[type - 0x2d][0]; f->bh = astc[type - 0x2d][1]; f->bpp = 16; return 1; }
    return 0;
}

static uint8_t f2u8(float v) { v = v < 0 ? 0 : v > 1 ? 1 : v; return (uint8_t)(v * 255.0f + 0.5f); }

static const char *decode_job(const char *blob, long off, long size, int fmt, int w, int h, int bhl,
                              const int sw[4], const char *out) {
    int type = fmt >> 8, var = fmt & 0xFF;
    fmtinfo fi;
    if (!fmt_info(type, &fi)) return "unsupported_format";
    FILE *f = fopen(blob, "rb");
    if (!f) return "open_blob";
    uint8_t *src = malloc(size);
    fseek(f, off, SEEK_SET);
    if (fread(src, 1, size, f) != (size_t)size) { fclose(f); free(src); return "short_read"; }
    fclose(f);
    uint32_t wb = div_up(w, fi.bw), hb = div_up(h, fi.bh);
    uint8_t *lin = malloc((size_t)wb * hb * fi.bpp);
    if (!deswizzle(src, size, lin, wb, hb, fi.bpp, 1u << bhl)) { free(src); free(lin); return "deswizzle_oob"; }
    free(src);
    int sgn = var == 0x02;
    uint8_t *rgba = calloc((size_t)w * h, 4);
    if (type == 0x1f) { // BC6H -> HDR
        float *hdr = malloc((size_t)w * h * 3 * sizeof(float));
        float blk[16 * 3];
        for (uint32_t by = 0; by < hb; by++) for (uint32_t bx = 0; bx < wb; bx++) {
            bcdec_bc6h_float(lin + (by * wb + bx) * 16, blk, 4 * 3, var == 0x05);
            for (int y = 0; y < 4; y++) for (int x = 0; x < 4; x++) {
                int px = bx * 4 + x, py = by * 4 + y;
                if (px < w && py < h) memcpy(hdr + ((size_t)py * w + px) * 3, blk + (y * 4 + x) * 3, 12);
            }
        }
        int ok = stbi_write_hdr(out, w, h, 3, hdr);
        free(hdr); free(lin); free(rgba);
        return ok ? NULL : "write";
    }
    uint8_t blk[12 * 12 * 4];
    for (uint32_t by = 0; by < hb; by++) for (uint32_t bx = 0; bx < wb; bx++) {
        const uint8_t *b = lin + ((size_t)by * wb + bx) * fi.bpp;
        memset(blk, 0, sizeof blk);
        int n = fi.bw * fi.bh;
        switch (type) {
        case 0x1a: bcdec_bc1(b, blk, 16); break;
        case 0x1b: bcdec_bc2(b, blk, 16); break;
        case 0x1c: bcdec_bc3(b, blk, 16); break;
        case 0x20: bcdec_bc7(b, blk, 16); break;
        case 0x1d: { float t[16]; bcdec_bc4_float(b, t, 4, sgn);
            for (int i = 0; i < 16; i++) { blk[i*4] = f2u8(sgn ? t[i] * 0.5f + 0.5f : t[i]); blk[i*4+3] = 255; } break; }
        case 0x1e: { float t[32]; bcdec_bc5_float(b, t, 8, sgn);
            for (int i = 0; i < 16; i++) {
                blk[i*4] = f2u8(sgn ? t[i*2] * 0.5f + 0.5f : t[i*2]);
                blk[i*4+1] = f2u8(sgn ? t[i*2+1] * 0.5f + 0.5f : t[i*2+1]); blk[i*4+3] = 255; } break; }
        case 0x02: blk[0] = b[0]; blk[3] = 255; break;
        case 0x09: blk[0] = b[0]; blk[1] = b[1]; blk[3] = 255; break;
        case 0x07: { uint16_t v = b[0] | b[1] << 8;
            blk[0] = ((v >> 11) & 31) * 255 / 31; blk[1] = ((v >> 5) & 63) * 255 / 63; blk[2] = (v & 31) * 255 / 31; blk[3] = 255; break; }
        case 0x0b: memcpy(blk, b, 4); break;
        case 0x0c: blk[0] = b[2]; blk[1] = b[1]; blk[2] = b[0]; blk[3] = b[3]; break;
        case 0x0e: { uint32_t v = b[0] | b[1] << 8 | b[2] << 16 | (uint32_t)b[3] << 24;
            blk[0] = (v & 1023) >> 2; blk[1] = ((v >> 10) & 1023) >> 2; blk[2] = ((v >> 20) & 1023) >> 2; blk[3] = (v >> 30) * 85; break; }
        default: decode_astc_block(b, fi.bw, fi.bh, var == 0x06, blk); break;
        }
        for (int y = 0; y < fi.bh; y++) for (int x = 0; x < fi.bw; x++) {
            int px = bx * fi.bw + x, py = by * fi.bh + y;
            if (px >= w || py >= h) continue;
            const uint8_t *s = blk + (y * fi.bw + x) * 4;
            uint8_t *d = rgba + ((size_t)py * w + px) * 4;
            for (int c = 0; c < 4; c++) {
                int k = sw[c];
                d[c] = k == 0 ? 0 : k == 1 ? 255 : (k >= 2 && k <= 5) ? s[k - 2] : s[c];
            }
        }
        (void)n;
    }
    int ok = stbi_write_png(out, w, h, 4, rgba, w * 4);
    free(lin); free(rgba);
    return ok ? NULL : "write";
}

int main(void) {
    char line[4096], blob[2048], out[2048];
    long off, size; int fmt, w, h, bhl, sw[4];
    stbi_write_png_compression_level = 6;
    while (fgets(line, sizeof line, stdin)) {
        if (sscanf(line, "%2047s %ld %ld %d %d %d %d %d %d %d %d %2047s", blob, &off, &size, &fmt, &w, &h, &bhl,
                   &sw[0], &sw[1], &sw[2], &sw[3], out) != 12) { printf("ERR parse -\n"); continue; }
        const char *e = decode_job(blob, off, size, fmt, w, h, bhl, sw, out);
        if (e) printf("ERR %s %s\n", e, out); else printf("OK %s\n", out);
        fflush(stdout);
    }
    return 0;
}
