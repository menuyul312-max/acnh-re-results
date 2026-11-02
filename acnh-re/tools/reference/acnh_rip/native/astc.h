// ASTC LDR 2D block decoder (Khronos ASTC specification, section C.2).
// decode_astc_block() writes bw*bh RGBA8 texels; error blocks become magenta.
#pragma once
#include <stdint.h>
#include <string.h>

typedef struct { const uint8_t *b; } astc_bits;

static int astc_getbits(const uint8_t *blk, int pos, int n) {
    int v = 0;
    for (int i = 0; i < n; i++) {
        int p = pos + i;
        if (p < 0 || p >= 128) continue;
        v |= ((blk[p >> 3] >> (p & 7)) & 1) << i;
    }
    return v;
}

// --- integer sequence encoding --------------------------------------------
// quant level index -> (trits, quints, bits)
static const int ASTC_LEVELS[21] = {2,3,4,5,6,8,10,12,16,20,24,32,40,48,64,80,96,128,160,192,256};
static void astc_level_enc(int levels, int *t, int *q, int *n) {
    *t = *q = 0;
    switch (levels) {
    case 2: *n = 1; break; case 3: *t = 1; *n = 0; break; case 4: *n = 2; break;
    case 5: *q = 1; *n = 0; break; case 6: *t = 1; *n = 1; break; case 8: *n = 3; break;
    case 10: *q = 1; *n = 1; break; case 12: *t = 1; *n = 2; break; case 16: *n = 4; break;
    case 20: *q = 1; *n = 2; break; case 24: *t = 1; *n = 3; break; case 32: *n = 5; break;
    case 40: *q = 1; *n = 3; break; case 48: *t = 1; *n = 4; break; case 64: *n = 6; break;
    case 80: *q = 1; *n = 4; break; case 96: *t = 1; *n = 5; break; case 128: *n = 7; break;
    case 160: *q = 1; *n = 5; break; case 192: *t = 1; *n = 6; break; default: *n = 8; break;
    }
}
static int astc_ise_bits(int count, int levels) {
    int t, q, n; astc_level_enc(levels, &t, &q, &n);
    if (t) return count * n + (8 * count + 4) / 5;
    if (q) return count * n + (7 * count + 2) / 3;
    return count * n;
}
static void astc_trit_decode(int T, int *t) {
    int C, t4, t3, t2, t1, t0;
    #define B(x, i) (((x) >> (i)) & 1)
    if (((T >> 2) & 7) == 7) {
        C = (((T >> 5) & 7) << 2) | (T & 3); t4 = 2; t3 = 2;
    } else {
        C = T & 0x1F;
        if (((T >> 5) & 3) == 3) { t4 = 2; t3 = B(T, 7); }
        else { t4 = B(T, 7); t3 = (T >> 5) & 3; }
    }
    if ((C & 3) == 3) { t2 = 2; t1 = B(C, 4); t0 = (B(C, 3) << 1) | (B(C, 2) & !B(C, 3)); }
    else if (((C >> 2) & 3) == 3) { t2 = 2; t1 = 2; t0 = C & 3; }
    else { t2 = B(C, 4); t1 = (C >> 2) & 3; t0 = (B(C, 1) << 1) | (B(C, 0) & !B(C, 1)); }
    t[0] = t0; t[1] = t1; t[2] = t2; t[3] = t3; t[4] = t4;
}
static void astc_quint_decode(int Q, int *q) {
    int C, q2, q1, q0;
    if (((Q >> 1) & 3) == 3 && ((Q >> 5) & 3) == 0) {
        q2 = (B(Q, 0) << 2) | ((B(Q, 4) & !B(Q, 0)) << 1) | (B(Q, 3) & !B(Q, 0));
        q1 = 4; q0 = 4;
    } else {
        if (((Q >> 1) & 3) == 3) {
            q2 = 4;
            C = (((Q >> 3) & 3) << 3) | ((~(Q >> 5) & 3) << 1) | B(Q, 0);
        } else {
            q2 = (Q >> 5) & 3; C = Q & 0x1F;
        }
        if ((C & 7) == 5) { q1 = 4; q0 = (C >> 3) & 3; }
        else { q1 = (C >> 3) & 3; q0 = C & 7; }
    }
    q[0] = q0; q[1] = q1; q[2] = q2;
    #undef B
}
// Decode `count` values; out[i] = (D << n) | m  and also returns m / D split.
static void astc_ise_decode(const uint8_t *blk, int pos, int count, int levels, int *vals, int *ms, int *ds) {
    int t, q, n; astc_level_enc(levels, &t, &q, &n);
    if (t) {
        static const int tb[5] = {2, 2, 1, 2, 1};
        for (int g = 0; g < count; g += 5) {
            int m[5] = {0}, T = 0, sh = 0;
            for (int i = 0; i < 5; i++) {
                m[i] = astc_getbits(blk, pos, n); pos += n;
                T |= astc_getbits(blk, pos, tb[i]) << sh; pos += tb[i]; sh += tb[i];
            }
            int tv[5]; astc_trit_decode(T, tv);
            for (int i = 0; i < 5 && g + i < count; i++) { ms[g + i] = m[i]; ds[g + i] = tv[i]; vals[g + i] = (tv[i] << n) | m[i]; }
        }
    } else if (q) {
        static const int qb[3] = {3, 2, 2};
        for (int g = 0; g < count; g += 3) {
            int m[3] = {0}, Q = 0, sh = 0;
            for (int i = 0; i < 3; i++) {
                m[i] = astc_getbits(blk, pos, n); pos += n;
                Q |= astc_getbits(blk, pos, qb[i]) << sh; pos += qb[i]; sh += qb[i];
            }
            int qv[3]; astc_quint_decode(Q, qv);
            for (int i = 0; i < 3 && g + i < count; i++) { ms[g + i] = m[i]; ds[g + i] = qv[i]; vals[g + i] = (qv[i] << n) | m[i]; }
        }
    } else {
        for (int i = 0; i < count; i++) { ms[i] = astc_getbits(blk, pos, n); ds[i] = 0; vals[i] = ms[i]; pos += n; }
    }
}

// Build B from a pattern like "b000b0bb0" (MSB first) using bits of m (a=bit0,b=bit1,...).
static int astc_pattern(const char *pat, int m) {
    int v = 0;
    for (const char *p = pat; *p; p++) {
        v <<= 1;
        if (*p >= 'a' && *p <= 'f') v |= (m >> (*p - 'a')) & 1;
    }
    return v;
}
static int astc_unq_color(int levels, int m, int D) {
    int t, q, n; astc_level_enc(levels, &t, &q, &n);
    if (!t && !q) { // bit replication to 8 bits
        int v = 0, filled = 0;
        while (filled < 8) { int s = 8 - filled - n; v |= s >= 0 ? m << s : m >> -s; filled += n; }
        return v & 0xFF;
    }
    int A = (m & 1) ? 0x1FF : 0, Bv = 0, C = 0;
    if (t) {
        switch (n) {
        case 1: C = 204; break;
        case 2: Bv = astc_pattern("b000b0bb0", m); C = 93; break;
        case 3: Bv = astc_pattern("cb000cbcb", m); C = 44; break;
        case 4: Bv = astc_pattern("dcb000dcb", m); C = 22; break;
        case 5: Bv = astc_pattern("edcb000ed", m); C = 11; break;
        case 6: Bv = astc_pattern("fedcb000f", m); C = 5; break;
        }
    } else {
        switch (n) {
        case 1: C = 113; break;
        case 2: Bv = astc_pattern("b0000bb00", m); C = 54; break;
        case 3: Bv = astc_pattern("cb0000cbc", m); C = 26; break;
        case 4: Bv = astc_pattern("dcb0000dc", m); C = 13; break;
        case 5: Bv = astc_pattern("edcb0000e", m); C = 6; break;
        }
    }
    int T = D * C + Bv; T ^= A; T = (A & 0x80) | (T >> 2);
    return T & 0xFF;
}
static int astc_unq_weight(int levels, int m, int D) {
    int t, q, n; astc_level_enc(levels, &t, &q, &n);
    int T;
    if (!t && !q) {
        int v = 0, filled = 0;
        while (filled < 6) { int s = 6 - filled - n; v |= s >= 0 ? m << s : m >> -s; filled += n; }
        T = v & 0x3F;
    } else if (n == 0) {
        T = t ? (int[]){0, 32, 63}[D] : (int[]){0, 16, 32, 47, 63}[D];
    } else {
        int A = (m & 1) ? 0x7F : 0, Bv = 0, C = 0;
        if (t) {
            if (n == 1) C = 50;
            else if (n == 2) { Bv = astc_pattern("b000b0b", m); C = 23; }
            else { Bv = astc_pattern("cb000cb", m); C = 11; }
        } else {
            if (n == 1) C = 28;
            else { Bv = astc_pattern("b0000b0", m); C = 13; }
        }
        T = D * C + Bv; T ^= A; T = (A & 0x20) | (T >> 2);
    }
    if (T > 32) T += 1;
    return T;
}

// --- partitions ---------------------------------------------------------
static uint32_t astc_hash52(uint32_t p) {
    p ^= p >> 15; p -= p << 17; p += p << 7; p += p << 4; p ^= p >> 5;
    p += p << 16; p ^= p >> 7; p ^= p >> 3; p ^= p << 6; p ^= p >> 17;
    return p;
}
static int astc_select_partition(int seed, int x, int y, int z, int pc, int small) {
    if (small) { x <<= 1; y <<= 1; z <<= 1; }
    seed += (pc - 1) * 1024;
    uint32_t r = astc_hash52((uint32_t)seed);
    uint8_t s[13];
    s[1] = r & 0xF; s[2] = (r >> 4) & 0xF; s[3] = (r >> 8) & 0xF; s[4] = (r >> 12) & 0xF;
    s[5] = (r >> 16) & 0xF; s[6] = (r >> 20) & 0xF; s[7] = (r >> 24) & 0xF; s[8] = (r >> 28) & 0xF;
    s[9] = (r >> 18) & 0xF; s[10] = (r >> 22) & 0xF; s[11] = (r >> 26) & 0xF;
    s[12] = ((r >> 30) | (r << 2)) & 0xF;
    for (int i = 1; i <= 12; i++) s[i] = (uint8_t)(s[i] * s[i]);
    int sh1, sh2, sh3;
    if (seed & 1) { sh1 = (seed & 2) ? 4 : 5; sh2 = (pc == 3) ? 6 : 5; }
    else { sh1 = (pc == 3) ? 6 : 5; sh2 = (seed & 2) ? 4 : 5; }
    sh3 = (seed & 0x10) ? sh1 : sh2;
    s[1] >>= sh1; s[2] >>= sh2; s[3] >>= sh1; s[4] >>= sh2; s[5] >>= sh1; s[6] >>= sh2;
    s[7] >>= sh1; s[8] >>= sh2; s[9] >>= sh3; s[10] >>= sh3; s[11] >>= sh3; s[12] >>= sh3;
    int a = s[1] * x + s[2] * y + s[11] * z + (r >> 14);
    int b = s[3] * x + s[4] * y + s[12] * z + (r >> 10);
    int c = s[5] * x + s[6] * y + s[9] * z + (r >> 6);
    int d = s[7] * x + s[8] * y + s[10] * z + (r >> 2);
    a &= 0x3F; b &= 0x3F; c &= 0x3F; d &= 0x3F;
    if (pc < 4) d = 0;
    if (pc < 3) c = 0;
    if (a >= b && a >= c && a >= d) return 0;
    if (b >= c && b >= d) return 1;
    if (c >= d) return 2;
    return 3;
}

// --- endpoints ----------------------------------------------------------
static int astc_clamp(int v) { return v < 0 ? 0 : v > 255 ? 255 : v; }
static void astc_bts(int *a, int *b) { *b >>= 1; *b |= *a & 0x80; *a >>= 1; *a &= 0x3F; if (*a & 0x20) *a -= 0x40; }
static void astc_bc(int *c) { c[0] = (c[0] + c[2]) >> 1; c[1] = (c[1] + c[2]) >> 1; }

// returns 0 on unsupported (HDR) mode
static int astc_endpoints(int cem, const int *v, int e0[4], int e1[4]) {
    int a, b;
    switch (cem) {
    case 0: e0[0]=e0[1]=e0[2]=v[0]; e0[3]=255; e1[0]=e1[1]=e1[2]=v[1]; e1[3]=255; return 1;
    case 1: { int L0 = (v[0] >> 2) | (v[1] & 0xC0); int L1 = L0 + (v[1] & 0x3F); if (L1 > 255) L1 = 255;
              e0[0]=e0[1]=e0[2]=L0; e0[3]=255; e1[0]=e1[1]=e1[2]=L1; e1[3]=255; return 1; }
    case 4: e0[0]=e0[1]=e0[2]=v[0]; e0[3]=v[2]; e1[0]=e1[1]=e1[2]=v[1]; e1[3]=v[3]; return 1;
    case 5: { int v0=v[0],v1=v[1],v2=v[2],v3=v[3]; astc_bts(&v1,&v0); astc_bts(&v3,&v2);
              e0[0]=e0[1]=e0[2]=v0; e0[3]=v2; int l=astc_clamp(v0+v1); e1[0]=e1[1]=e1[2]=l; e1[3]=astc_clamp(v2+v3); return 1; }
    case 6: e0[0]=(v[0]*v[3])>>8; e0[1]=(v[1]*v[3])>>8; e0[2]=(v[2]*v[3])>>8; e0[3]=255;
            e1[0]=v[0]; e1[1]=v[1]; e1[2]=v[2]; e1[3]=255; return 1;
    case 8: case 12: {
        int s0 = v[0]+v[2]+v[4], s1 = v[1]+v[3]+v[5];
        int al0 = cem == 12 ? v[6] : 255, al1 = cem == 12 ? v[7] : 255;
        if (s1 >= s0) { e0[0]=v[0]; e0[1]=v[2]; e0[2]=v[4]; e0[3]=al0; e1[0]=v[1]; e1[1]=v[3]; e1[2]=v[5]; e1[3]=al1; }
        else { e0[0]=v[1]; e0[1]=v[3]; e0[2]=v[5]; e0[3]=al1; astc_bc(e0); e1[0]=v[0]; e1[1]=v[2]; e1[2]=v[4]; e1[3]=al0; astc_bc(e1); }
        return 1; }
    case 9: case 13: {
        int w[8]; for (int i = 0; i < 8; i++) w[i] = v[i];
        astc_bts(&w[1],&w[0]); astc_bts(&w[3],&w[2]); astc_bts(&w[5],&w[4]);
        if (cem == 13) astc_bts(&w[7],&w[6]);
        int al0 = cem == 13 ? w[6] : 255, al1 = cem == 13 ? astc_clamp(w[6]+w[7]) : 255;
        if (w[1]+w[3]+w[5] >= 0) {
            e0[0]=w[0]; e0[1]=w[2]; e0[2]=w[4]; e0[3]=al0;
            e1[0]=astc_clamp(w[0]+w[1]); e1[1]=astc_clamp(w[2]+w[3]); e1[2]=astc_clamp(w[4]+w[5]); e1[3]=al1;
        } else {
            e0[0]=astc_clamp(w[0]+w[1]); e0[1]=astc_clamp(w[2]+w[3]); e0[2]=astc_clamp(w[4]+w[5]); e0[3]=al1; astc_bc(e0);
            e1[0]=w[0]; e1[1]=w[2]; e1[2]=w[4]; e1[3]=al0; astc_bc(e1);
        }
        (void)a; (void)b;
        return 1; }
    case 10: e0[0]=(v[0]*v[3])>>8; e0[1]=(v[1]*v[3])>>8; e0[2]=(v[2]*v[3])>>8; e0[3]=v[4];
             e1[0]=v[0]; e1[1]=v[1]; e1[2]=v[2]; e1[3]=v[5]; return 1;
    }
    return 0;
}

static void astc_error(uint8_t *out, int n) {
    for (int i = 0; i < n; i++) { out[i*4]=255; out[i*4+1]=0; out[i*4+2]=255; out[i*4+3]=255; }
}

static void decode_astc_block(const uint8_t *blk, int bw, int bh, int srgb, uint8_t *out) {
    int texels = bw * bh;
    int mode = astc_getbits(blk, 0, 11);
    if ((mode & 0x1FF) == 0x1FC) { // void extent
        if (mode & 0x200) { astc_error(out, texels); return; } // HDR
        int c[4]; for (int i = 0; i < 4; i++) c[i] = astc_getbits(blk, 64 + 16 * i, 16) >> 8;
        for (int i = 0; i < texels; i++) for (int k = 0; k < 4; k++) out[i*4+k] = (uint8_t)c[k];
        return;
    }
    int R, Hp, D, W, Hh;
    #define BT(i) ((mode >> (i)) & 1)
    if (mode & 3) {
        R = BT(4) | ((mode & 3) << 1); Hp = BT(9); D = BT(10);
        int A = (mode >> 5) & 3, Bq = (mode >> 7) & 3;
        switch ((mode >> 2) & 3) {
        case 0: W = Bq + 4; Hh = A + 2; break;
        case 1: W = Bq + 8; Hh = A + 2; break;
        case 2: W = A + 2; Hh = Bq + 8; break;
        default:
            if (BT(8)) { W = BT(7) + 2; Hh = A + 2; } else { W = A + 2; Hh = BT(7) + 6; }
        }
    } else {
        if ((mode & 0xF) == 0) { astc_error(out, texels); return; } // reserved
        R = BT(4) | (((mode >> 2) & 3) << 1); Hp = BT(9); D = BT(10);
        int A = (mode >> 5) & 3, Bq = (mode >> 9) & 3;
        switch ((mode >> 7) & 3) {
        case 0: W = 12; Hh = A + 2; break;
        case 1: W = A + 2; Hh = 12; break;
        case 2: W = A + 6; Hh = Bq + 6; D = 0; Hp = 0; break;
        default:
            if (A == 0) { W = 6; Hh = 10; } else if (A == 1) { W = 10; Hh = 6; }
            else { astc_error(out, texels); return; }
        }
    }
    #undef BT
    // weight range table (spec C.2.7): levels by (H, R)
    static const int wl0[8] = {0, 0, 2, 3, 4, 5, 6, 8}, wl1[8] = {0, 0, 10, 12, 16, 20, 24, 32};
    int wlevels = Hp ? wl1[R] : wl0[R];
    if (!wlevels || W > bw || Hh > bh) { astc_error(out, texels); return; }
    int nweights = W * Hh * (D + 1);
    int wbits = astc_ise_bits(nweights, wlevels);
    if (nweights > 64 || wbits < 24 || wbits > 96) { astc_error(out, texels); return; }

    int pc = astc_getbits(blk, 11, 2) + 1;
    if (D && pc == 4) { astc_error(out, texels); return; }
    int cem[4], seed = 0, color_start, below = 128 - wbits;
    if (pc == 1) {
        cem[0] = astc_getbits(blk, 13, 4); color_start = 17;
    } else {
        seed = astc_getbits(blk, 13, 10);
        int cemf = astc_getbits(blk, 23, 6);
        color_start = 29;
        if ((cemf & 3) == 0) {
            for (int i = 0; i < pc; i++) cem[i] = cemf >> 2;
        } else {
            int extra = 3 * pc - 4;
            below -= extra;
            int full = (cemf >> 2) | (astc_getbits(blk, below, extra) << 4);
            int base = (cemf & 3) - 1;
            for (int i = 0; i < pc; i++) {
                int c = (full >> i) & 1;
                int m = (full >> (pc + 2 * i)) & 3;
                cem[i] = ((base + c) << 2) | m;
            }
        }
    }
    int ccs = 0;
    if (D) { below -= 2; ccs = astc_getbits(blk, below, 2); }
    int ncolor = 0;
    for (int i = 0; i < pc; i++) ncolor += 2 * ((cem[i] >> 2) + 1);
    if (ncolor > 18) { astc_error(out, texels); return; }
    int avail = below - color_start, clevels = 0;
    for (int i = 20; i >= 0; i--)
        if (astc_ise_bits(ncolor, ASTC_LEVELS[i]) <= avail) { clevels = ASTC_LEVELS[i]; break; }
    if (clevels < 6) { astc_error(out, texels); return; }

    int cv[18], cm[18], cd[18];
    astc_ise_decode(blk, color_start, ncolor, clevels, cv, cm, cd);
    for (int i = 0; i < ncolor; i++) cv[i] = astc_unq_color(clevels, cm[i], cd[i]);

    int ep[4][2][4], k = 0;
    for (int i = 0; i < pc; i++) {
        if (!astc_endpoints(cem[i], cv + k, ep[i][0], ep[i][1])) { astc_error(out, texels); return; }
        k += 2 * ((cem[i] >> 2) + 1);
    }

    // weights are stored bit-reversed from the top of the block
    uint8_t rev[16];
    for (int i = 0; i < 16; i++) {
        uint8_t x = blk[15 - i], r = 0;
        for (int j = 0; j < 8; j++) r |= ((x >> j) & 1) << (7 - j);
        rev[i] = r;
    }
    int wv[64], wm[64], wd[64];
    astc_ise_decode(rev, 0, nweights, wlevels, wv, wm, wd);
    for (int i = 0; i < nweights; i++) wv[i] = astc_unq_weight(wlevels, wm[i], wd[i]);

    int Ds = (1024 + bw / 2) / (bw - 1), Dt = (1024 + bh / 2) / (bh - 1);
    int small = texels < 31;
    for (int t = 0; t < bh; t++) for (int s = 0; s < bw; s++) {
        int cs = Ds * s, ct = Dt * t;
        int gs = (cs * (W - 1) + 32) >> 6, gt = (ct * (Hh - 1) + 32) >> 6;
        int js = gs >> 4, fs = gs & 0xF, jt = gt >> 4, ft = gt & 0xF;
        int w11 = (fs * ft + 8) >> 4, w10 = ft - w11, w01 = fs - w11, w00 = 16 - fs - ft + w11;
        int pw[2];
        for (int p = 0; p <= D; p++) {
            int v0 = js + jt * W;
            #define WV(idx) wv[((idx) < W * Hh ? (idx) : W * Hh - 1) * (D + 1) + p]
            int p00 = WV(v0), p01 = (js + 1 < W) ? WV(v0 + 1) : 0;
            int p10 = (jt + 1 < Hh) ? WV(v0 + W) : 0, p11 = (js + 1 < W && jt + 1 < Hh) ? WV(v0 + W + 1) : 0;
            #undef WV
            pw[p] = (p00 * w00 + p01 * w01 + p10 * w10 + p11 * w11 + 8) >> 4;
        }
        int part = pc > 1 ? astc_select_partition(seed, s, t, 0, pc, small) : 0;
        uint8_t *o = out + (t * bw + s) * 4;
        for (int c = 0; c < 4; c++) {
            int w = (D && c == ccs) ? pw[1] : pw[0];
            int c0 = ep[part][0][c], c1 = ep[part][1][c];
            if (srgb) { c0 = (c0 << 8) | 0x80; c1 = (c1 << 8) | 0x80; }
            else { c0 = (c0 << 8) | c0; c1 = (c1 << 8) | c1; }
            int C = (c0 * (64 - w) + c1 * w + 32) >> 6;
            o[c] = (uint8_t)(C >> 8);
        }
    }
}
