// BWAV -> 16-bit PCM WAV.   bwavdec <in.bwav> <offset> <out.wav>
// Channel info (0x4C each, from 0x10): +0x00 u16 codec (0 PCM16, 1 DSP-ADPCM),
// +0x04 u32 rate, +0x08 u32 samples, +0x10 s16 coefs[16], +0x30 u32 data offset,
// +0x38 u32 loop flag, +0x3C u32 loop end, +0x40 u32 loop start.
// Prints: META <channels> <rate> <samples> <codec> <loop> <loop_start> <loop_end>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

static uint16_t rd16(const uint8_t *p) { return p[0] | p[1] << 8; }
static uint32_t rd32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static int16_t clamp16(int v) { return v > 32767 ? 32767 : v < -32768 ? -32768 : v; }

static void dsp_decode(const uint8_t *src, size_t avail, uint32_t n, const int16_t *coef, int16_t *dst) {
    int h1 = 0, h2 = 0;
    uint32_t i = 0; size_t p = 0;
    while (i < n && p < avail) {
        uint8_t hdr = src[p++];
        int scale = 1 << (hdr & 0xF), pred = hdr >> 4;
        int c1 = coef[pred * 2], c2 = coef[pred * 2 + 1];
        for (int k = 0; k < 14 && i < n; k++) {
            if (p >= avail) return;
            int nib = (k & 1) ? (src[p++] & 0xF) : (src[p] >> 4);
            if (nib >= 8) nib -= 16;
            int s = ((nib * scale) << 11) + 1024 + c1 * h1 + c2 * h2;
            int16_t v = clamp16(s >> 11);
            dst[i++] = v; h2 = h1; h1 = v;
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 4) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *d = malloc(len);
    if (fread(d, 1, len, f) != (size_t)len) return 1;
    fclose(f);
    long base = atol(argv[2]);
    const uint8_t *b = d + base;
    if (memcmp(b, "BWAV", 4)) { printf("ERR magic\n"); return 1; }
    int nch = rd16(b + 0xE);
    const uint8_t *c0 = b + 0x10;
    uint32_t rate = rd32(c0 + 4), ns = rd32(c0 + 8);
    int codec = rd16(c0);
    uint32_t loop = rd32(c0 + 0x38), lend = rd32(c0 + 0x3C), lstart = rd32(c0 + 0x40);
    int16_t *pcm = calloc((size_t)ns * nch, 2), *tmp = calloc(ns, 2);
    for (int c = 0; c < nch; c++) {
        const uint8_t *ci = b + 0x10 + c * 0x4C;
        uint32_t off = rd32(ci + 0x30);
        if (base + off >= len) { printf("ERR offset\n"); return 1; }
        size_t avail = len - base - off;
        if (codec == 1) {
            int16_t coef[16];
            for (int k = 0; k < 16; k++) coef[k] = (int16_t)rd16(ci + 0x10 + k * 2);
            dsp_decode(b + off, avail, ns, coef, tmp);
        } else if (codec == 0) {
            for (uint32_t i = 0; i < ns && i * 2 + 1 < avail; i++) tmp[i] = (int16_t)rd16(b + off + i * 2);
        } else { printf("ERR codec %d\n", codec); return 1; }
        for (uint32_t i = 0; i < ns; i++) pcm[(size_t)i * nch + c] = tmp[i];
    }
    FILE *o = fopen(argv[3], "wb");
    uint32_t data = ns * nch * 2;
    uint8_t h[44];
    memcpy(h, "RIFF", 4); uint32_t v = 36 + data; memcpy(h + 4, &v, 4); memcpy(h + 8, "WAVEfmt ", 8);
    v = 16; memcpy(h + 16, &v, 4); uint16_t s = 1; memcpy(h + 20, &s, 2); s = nch; memcpy(h + 22, &s, 2);
    memcpy(h + 24, &rate, 4); v = rate * nch * 2; memcpy(h + 28, &v, 4); s = nch * 2; memcpy(h + 32, &s, 2);
    s = 16; memcpy(h + 34, &s, 2); memcpy(h + 36, "data", 4); memcpy(h + 40, &data, 4);
    fwrite(h, 1, 44, o); fwrite(pcm, 2, (size_t)ns * nch, o); fclose(o);
    printf("META %d %u %u %d %u %u %u\n", nch, rate, ns, codec, loop, lstart, lend);
    return 0;
}
