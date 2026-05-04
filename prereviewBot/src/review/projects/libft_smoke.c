/* prereviewBot libft smoke test (fsoares-inspired strict edition)
 *
 * Compiled and linked against the student's libft.a; run twice — once with
 * -fsanitize=address,undefined for behaviour + UB + OOB detection, once under
 * valgrind for leak detection.
 *
 * Failures are printed to stderr; the binary exits non-zero if anything
 * deviates from the v19.2 subject. Tests favour boundary values, canary
 * buffers (to catch out-of-bounds writes), and full-range comparisons against
 * libc for ctype/case-conversion functions.
 */

#define _GNU_SOURCE

#include "libft.h"

#include <ctype.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

static int g_failures;

#define FAIL(fmt, ...)                                                      \
    do {                                                                    \
        fprintf(stderr, "FAIL %s:%d: " fmt "\n", __FILE__, __LINE__,        \
                ##__VA_ARGS__);                                             \
        g_failures++;                                                       \
    } while (0)

#define CHECK(expr)                                                         \
    do {                                                                    \
        if (!(expr)) FAIL("%s", #expr);                                     \
    } while (0)

#define CHECK_INT(actual, expected)                                         \
    do {                                                                    \
        long _a = (long)(actual);                                           \
        long _e = (long)(expected);                                         \
        if (_a != _e) FAIL("%s -> %ld, expected %ld", #actual, _a, _e);     \
    } while (0)

#define CHECK_STR(actual, expected)                                         \
    do {                                                                    \
        const char *_a = (actual);                                          \
        const char *_e = (expected);                                        \
        if (!_a || !_e || strcmp(_a, _e) != 0)                              \
            FAIL("%s -> \"%s\", expected \"%s\"",                           \
                 #actual, _a ? _a : "(null)", _e ? _e : "(null)");          \
    } while (0)

#define CHECK_MEM(actual, expected, n)                                      \
    do {                                                                    \
        if (memcmp((actual), (expected), (n)) != 0)                         \
            FAIL("memory differs: %s vs %s (n=%zu)",                        \
                 #actual, #expected, (size_t)(n));                          \
    } while (0)

#define CHECK_SIGN_EQ(actual, expected)                                     \
    do {                                                                    \
        int _a = (actual);                                                  \
        int _e = (expected);                                                \
        int _ka = (_a > 0) - (_a < 0);                                      \
        int _ke = (_e > 0) - (_e < 0);                                      \
        if (_ka != _ke)                                                     \
            FAIL("sign mismatch: %s -> %d, expected sign of %d",            \
                 #actual, _a, _e);                                          \
    } while (0)

/* ============= canary buffer helpers ============= */

#define CANARY 0xA5
#define CBUF_SIZE 64

static void cbuf_init(unsigned char *buf) {
    memset(buf, CANARY, CBUF_SIZE);
}

/* Verify every byte OUTSIDE [start, start+len) still holds the canary. */
static int cbuf_outside_clean(const unsigned char *buf, size_t start, size_t len) {
    for (size_t i = 0; i < CBUF_SIZE; i++) {
        if (i >= start && i < start + len) continue;
        if (buf[i] != CANARY) return 0;
    }
    return 1;
}

/* ============= Part 1: ctype ============= */

#define CTYPE_FULL_RANGE(ftname, libname)                                   \
    static void test_##ftname(void) {                                       \
        for (int c = -1; c <= 255; c++) {                                   \
            int got = ftname(c);                                            \
            int want = libname(c);                                          \
            int gb = got ? 1 : 0;                                           \
            int wb = want ? 1 : 0;                                          \
            if (gb != wb) FAIL(#ftname "(%d) -> %d, libc -> %d", c, got, want); \
        }                                                                   \
        /* subject: classification functions return 1 or 0, not non-zero. */ \
        if (libname('A')) CHECK_INT(ftname('A') > 0, 1);                    \
        if (libname('z')) CHECK_INT(ftname('z') > 0, 1);                    \
    }

CTYPE_FULL_RANGE(ft_isalpha, isalpha)
CTYPE_FULL_RANGE(ft_isdigit, isdigit)
CTYPE_FULL_RANGE(ft_isalnum, isalnum)
CTYPE_FULL_RANGE(ft_isascii, isascii)
CTYPE_FULL_RANGE(ft_isprint, isprint)

static void test_toupper_full(void) {
    for (int c = -1; c <= 255; c++) {
        if (ft_toupper(c) != toupper(c))
            FAIL("ft_toupper(%d) -> %d, libc -> %d", c, ft_toupper(c), toupper(c));
    }
}

static void test_tolower_full(void) {
    for (int c = -1; c <= 255; c++) {
        if (ft_tolower(c) != tolower(c))
            FAIL("ft_tolower(%d) -> %d, libc -> %d", c, ft_tolower(c), tolower(c));
    }
}

/* ============= Part 1: strlen ============= */

static void test_strlen(void) {
    CHECK_INT(ft_strlen(""), 0);
    CHECK_INT(ft_strlen("a"), 1);
    CHECK_INT(ft_strlen("hello"), 5);
    CHECK_INT(ft_strlen("42Tokyo"), 7);
    /* embedded high bytes should still terminate at '\0' */
    CHECK_INT(ft_strlen("\xff\xfe\x01"), 3);
}

/* ============= Part 1: memset / bzero ============= */

static void test_memset(void) {
    unsigned char buf[CBUF_SIZE];
    cbuf_init(buf);
    void *r = ft_memset(buf + 8, 'X', 16);
    CHECK(r == buf + 8);
    for (size_t i = 8; i < 24; i++) CHECK_INT(buf[i], 'X');
    CHECK(cbuf_outside_clean(buf, 8, 16));
    /* n = 0 must leave buffer untouched */
    cbuf_init(buf);
    ft_memset(buf, 'Z', 0);
    CHECK(cbuf_outside_clean(buf, 0, 0));
    /* high-byte value */
    cbuf_init(buf);
    ft_memset(buf, 0xFF, 4);
    for (int i = 0; i < 4; i++) CHECK_INT(buf[i], 0xFF);
}

static void test_bzero(void) {
    unsigned char buf[CBUF_SIZE];
    cbuf_init(buf);
    ft_bzero(buf + 4, 8);
    for (size_t i = 4; i < 12; i++) CHECK_INT(buf[i], 0);
    CHECK(cbuf_outside_clean(buf, 4, 8));
    /* n = 0 */
    cbuf_init(buf);
    ft_bzero(buf, 0);
    CHECK(cbuf_outside_clean(buf, 0, 0));
}

/* ============= Part 1: memcpy / memmove ============= */

static void test_memcpy(void) {
    unsigned char dst[CBUF_SIZE];
    cbuf_init(dst);
    void *r = ft_memcpy(dst + 4, "hello", 6);
    CHECK(r == dst + 4);
    CHECK_MEM(dst + 4, "hello", 6);
    CHECK(cbuf_outside_clean(dst, 4, 6));
    /* n = 0 — must not touch dst */
    cbuf_init(dst);
    ft_memcpy(dst, "X", 0);
    CHECK(cbuf_outside_clean(dst, 0, 0));
}

static void test_memmove(void) {
    /* forward overlap: copy [0..5) into [2..7) */
    unsigned char a[CBUF_SIZE];
    cbuf_init(a);
    memcpy(a, "hello world", 11);
    void *r = ft_memmove(a + 2, a, 5);
    CHECK(r == a + 2);
    CHECK_MEM(a, "hehello world" /* first 13 */, 13);
    /* backward overlap: copy [6..11) into [0..5) */
    unsigned char b[CBUF_SIZE];
    cbuf_init(b);
    memcpy(b, "hello world", 11);
    ft_memmove(b, b + 6, 5);
    CHECK_MEM(b, "world", 5);
    /* src == dst, n > 0 */
    unsigned char c[CBUF_SIZE];
    cbuf_init(c);
    memcpy(c, "abcd", 4);
    ft_memmove(c, c, 4);
    CHECK_MEM(c, "abcd", 4);
    /* n = 0 */
    unsigned char d[CBUF_SIZE];
    cbuf_init(d);
    ft_memmove(d, "X", 0);
    CHECK(cbuf_outside_clean(d, 0, 0));
}

/* ============= Part 1: strlcpy / strlcat ============= */

static void test_strlcpy(void) {
    unsigned char buf[CBUF_SIZE];
    /* truncation: dstsize=4, src="abcdefgh" -> "abc\0", returns 8 */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "abcdefgh", 4), 8);
    CHECK_MEM(buf, "abc", 4);
    CHECK(cbuf_outside_clean(buf, 0, 4));
    /* exact fit: dstsize=4, src="abc" */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "abc", 4), 3);
    CHECK_MEM(buf, "abc", 4);
    CHECK(cbuf_outside_clean(buf, 0, 4));
    /* dstsize=0 must NOT touch dst, return strlen(src) */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "anything", 0), 8);
    CHECK(cbuf_outside_clean(buf, 0, 0));
    /* dstsize=1 writes only '\0' */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "abc", 1), 3);
    CHECK_INT(buf[0], 0);
    CHECK(cbuf_outside_clean(buf, 0, 1));
    /* oversized buffer: must not write past terminator */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "ab", 32), 2);
    CHECK_MEM(buf, "ab", 3);
    CHECK(cbuf_outside_clean(buf, 0, 3));
    /* empty src */
    cbuf_init(buf);
    CHECK_INT(ft_strlcpy((char *)buf, "", 8), 0);
    CHECK_INT(buf[0], 0);
    CHECK(cbuf_outside_clean(buf, 0, 1));
}

static void test_strlcat(void) {
    unsigned char buf[CBUF_SIZE];
    /* normal append */
    cbuf_init(buf);
    memcpy(buf, "ab", 3);
    CHECK_INT(ft_strlcat((char *)buf, "cd", sizeof(buf)), 4);
    CHECK_MEM(buf, "abcd", 5);
    /* truncation */
    cbuf_init(buf);
    memcpy(buf, "ab", 3);
    CHECK_INT(ft_strlcat((char *)buf, "cdef", 5), 6);
    CHECK_MEM(buf, "abcd", 5);
    /* empty src must return current dstlen */
    cbuf_init(buf);
    memcpy(buf, "abc", 4);
    CHECK_INT(ft_strlcat((char *)buf, "", sizeof(buf)), 3);
    CHECK_MEM(buf, "abc", 4);
    /* dstsize <= initial dstlen: BSD strlcat returns dstsize + strlen(src),
     * dst untouched. */
    cbuf_init(buf);
    memcpy(buf, "abc", 4);
    CHECK_INT(ft_strlcat((char *)buf, "xy", 2), 4);
    CHECK_MEM(buf, "abc", 4);
}

/* ============= Part 1: strchr / strrchr ============= */

static void test_strchr(void) {
    const char *s = "tripouille";
    CHECK(ft_strchr(s, 't') == s);
    CHECK(ft_strchr(s, 'i') == s + 2);
    CHECK(ft_strchr(s, 'l') == s + 7);
    CHECK(ft_strchr(s, 'z') == NULL);
    /* subject: '\0' must point to terminator. */
    CHECK(ft_strchr(s, 0) == s + strlen(s));
    /* int param truncated to char */
    CHECK(ft_strchr(s, 't' + 256) == s);
}

static void test_strrchr(void) {
    const char *s = "tripouille";
    CHECK(ft_strrchr(s, 'i') == s + 8);
    CHECK(ft_strrchr(s, 'l') == s + 8 - 1);  /* second 'l' */
    CHECK(ft_strrchr(s, 't') == s);
    CHECK(ft_strrchr(s, 'z') == NULL);
    CHECK(ft_strrchr(s, 0) == s + strlen(s));
}

/* ============= Part 1: strncmp / memchr / memcmp ============= */

static void test_strncmp(void) {
    CHECK_INT(ft_strncmp("abc", "abc", 3), 0);
    CHECK_SIGN_EQ(ft_strncmp("abc", "abd", 3), -1);
    CHECK_SIGN_EQ(ft_strncmp("abd", "abc", 3), 1);
    CHECK_INT(ft_strncmp("abc", "abd", 2), 0);
    CHECK_INT(ft_strncmp("", "", 5), 0);
    CHECK_INT(ft_strncmp("abc", "abcd", 0), 0);
    CHECK_INT(ft_strncmp("abc", "abc", 100), 0);
    /* must compare as unsigned char (high-byte > low-byte) */
    CHECK_SIGN_EQ(ft_strncmp("\xff", "\x01", 1), 1);
    CHECK_SIGN_EQ(ft_strncmp("\x01", "\xff", 1), -1);
}

static void test_memchr(void) {
    const char *s = "hello";
    CHECK(ft_memchr(s, 'l', 5) == s + 2);
    CHECK(ft_memchr(s, 'z', 5) == NULL);
    CHECK(ft_memchr(s, 'l', 2) == NULL);
    CHECK(ft_memchr(s, 'h', 0) == NULL);
    /* binary data including '\0' (memchr doesn't stop at '\0') */
    const unsigned char data[] = {0x00, 0x01, 0xff, 0x42};
    CHECK(ft_memchr(data, 0xff, 4) == data + 2);
    CHECK(ft_memchr(data, 0x00, 4) == data);
}

static void test_memcmp(void) {
    CHECK_INT(ft_memcmp("abc", "abc", 3), 0);
    CHECK_SIGN_EQ(ft_memcmp("abc", "abd", 3), -1);
    CHECK_SIGN_EQ(ft_memcmp("abd", "abc", 3), 1);
    CHECK_INT(ft_memcmp("ab", "ac", 0), 0);
    /* unsigned char semantics */
    CHECK_SIGN_EQ(ft_memcmp("\xff", "\x01", 1), 1);
}

/* ============= Part 1: strnstr ============= */

static void test_strnstr(void) {
    const char *hay = "the quick brown fox";
    CHECK(ft_strnstr(hay, "quick", 19) == hay + 4);
    CHECK(ft_strnstr(hay, "quick", 9) == hay + 4);
    /* needle ends past `len` -> NULL */
    CHECK(ft_strnstr(hay, "quick", 8) == NULL);
    /* empty needle -> haystack */
    CHECK(ft_strnstr(hay, "", 5) == hay);
    /* needle longer than haystack */
    CHECK(ft_strnstr("hi", "hello", 5) == NULL);
    /* not found */
    CHECK(ft_strnstr(hay, "xyz", 19) == NULL);
    /* needle == haystack */
    CHECK(ft_strnstr("abc", "abc", 3) != NULL);
    /* large len must not walk past terminator */
    CHECK(ft_strnstr("abc", "d", (size_t)0xffffffff) == NULL);
}

/* ============= Part 1: atoi ============= */

static void test_atoi(void) {
    CHECK_INT(ft_atoi("0"), 0);
    CHECK_INT(ft_atoi("42"), 42);
    CHECK_INT(ft_atoi("  -42"), -42);
    CHECK_INT(ft_atoi("\t\n\v\f\r 123"), 123);
    CHECK_INT(ft_atoi("+123"), 123);
    CHECK_INT(ft_atoi("123abc"), 123);
    CHECK_INT(ft_atoi("--1"), 0);
    CHECK_INT(ft_atoi("+-1"), 0);
    CHECK_INT(ft_atoi("-+1"), 0);
    CHECK_INT(ft_atoi(""), 0);
    CHECK_INT(ft_atoi("   "), 0);
    CHECK_INT(ft_atoi("-"), 0);
    CHECK_INT(ft_atoi("2147483647"), INT_MAX);
    CHECK_INT(ft_atoi("-2147483648"), INT_MIN);
    CHECK_INT(ft_atoi("0000000042"), 42);
    CHECK_INT(ft_atoi("  +0"), 0);
}

/* ============= Part 1: calloc / strdup ============= */

static void test_calloc(void) {
    unsigned char *p = ft_calloc(8, sizeof(unsigned char));
    CHECK(p != NULL);
    if (p) {
        for (int i = 0; i < 8; i++) CHECK_INT(p[i], 0);
        free(p);
    }
    int *ip = ft_calloc(4, sizeof(int));
    CHECK(ip != NULL);
    if (ip) {
        for (int i = 0; i < 4; i++) CHECK_INT(ip[i], 0);
        free(ip);
    }
    /* subject: nmemb or size = 0 must return a unique freeable pointer. */
    void *z1 = ft_calloc(0, 0);
    CHECK(z1 != NULL);
    free(z1);
    void *z2 = ft_calloc(0, 64);
    CHECK(z2 != NULL);
    free(z2);
    void *z3 = ft_calloc(64, 0);
    CHECK(z3 != NULL);
    free(z3);
}

static void test_strdup(void) {
    char *d = ft_strdup("hello");
    CHECK(d != NULL);
    if (d) {
        CHECK_STR(d, "hello");
        free(d);
    }
    char *e = ft_strdup("");
    CHECK(e != NULL);
    if (e) {
        CHECK_STR(e, "");
        free(e);
    }
    char *f = ft_strdup("\xff\x01\x02");
    CHECK(f != NULL);
    if (f) {
        CHECK_INT((unsigned char)f[0], 0xff);
        CHECK_INT((unsigned char)f[1], 0x01);
        free(f);
    }
}

/* ============= Part 2: substr / strjoin / strtrim ============= */

static void test_substr(void) {
    char *s;
    s = ft_substr("hello world", 6, 5);  CHECK_STR(s, "world");      free(s);
    s = ft_substr("hello", 0, 100);      CHECK_STR(s, "hello");      free(s);
    s = ft_substr("hello", 10, 5);       CHECK(s != NULL); CHECK_STR(s, ""); free(s);
    /* start exactly at strlen */
    s = ft_substr("hello", 5, 5);        CHECK(s != NULL); CHECK_STR(s, ""); free(s);
    s = ft_substr("", 0, 100);           CHECK(s != NULL); CHECK_STR(s, ""); free(s);
    /* len=0 */
    s = ft_substr("hello", 1, 0);        CHECK(s != NULL); CHECK_STR(s, ""); free(s);
    /* very large len: must cap to actual remaining length */
    s = ft_substr("hello", 1, (size_t)-1); CHECK_STR(s, "ello"); free(s);
}

static void test_strjoin(void) {
    char *s;
    s = ft_strjoin("foo", "bar"); CHECK_STR(s, "foobar"); free(s);
    s = ft_strjoin("", "x");      CHECK_STR(s, "x");      free(s);
    s = ft_strjoin("y", "");      CHECK_STR(s, "y");      free(s);
    s = ft_strjoin("", "");       CHECK_STR(s, "");       free(s);
    /* long join */
    s = ft_strjoin("12345", "67890"); CHECK_STR(s, "1234567890"); free(s);
}

static void test_strtrim(void) {
    char *s;
    s = ft_strtrim("  hello  ", " ");      CHECK_STR(s, "hello"); free(s);
    s = ft_strtrim("xxhelloxx", "x");      CHECK_STR(s, "hello"); free(s);
    s = ft_strtrim("hello", "xyz");        CHECK_STR(s, "hello"); free(s);
    s = ft_strtrim("xxxx", "x");           CHECK_STR(s, "");      free(s);
    s = ft_strtrim("", "abc");             CHECK_STR(s, "");      free(s);
    /* multi-char trim set */
    s = ft_strtrim("[]hello[]", "[]");     CHECK_STR(s, "hello"); free(s);
    /* set is empty => no trim */
    s = ft_strtrim("hello", "");           CHECK_STR(s, "hello"); free(s);
    /* whitespace mix */
    s = ft_strtrim(" \t\nhello\t\n ", " \t\n"); CHECK_STR(s, "hello"); free(s);
}

/* ============= Part 2: split ============= */

static void free_split(char **parts) {
    if (!parts) return;
    for (int i = 0; parts[i]; i++) free(parts[i]);
    free(parts);
}

static void test_split(void) {
    char **parts;

    parts = ft_split("hello world foo", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "hello");
        CHECK_STR(parts[1], "world");
        CHECK_STR(parts[2], "foo");
        CHECK(parts[3] == NULL);
        free_split(parts);
    }

    /* leading + trailing + consecutive delimiters */
    parts = ft_split("   leading and trailing   ", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "leading");
        CHECK_STR(parts[1], "and");
        CHECK_STR(parts[2], "trailing");
        CHECK(parts[3] == NULL);
        free_split(parts);
    }

    /* all delimiters */
    parts = ft_split("     ", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK(parts[0] == NULL);
        free_split(parts);
    }

    /* empty input */
    parts = ft_split("", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK(parts[0] == NULL);
        free_split(parts);
    }

    /* single word */
    parts = ft_split("alone", ',');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "alone");
        CHECK(parts[1] == NULL);
        free_split(parts);
    }

    /* delimiter '\0' -> whole string is one element */
    parts = ft_split("abc", '\0');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "abc");
        CHECK(parts[1] == NULL);
        free_split(parts);
    }
}

/* ============= Part 2: itoa / strmapi / striteri ============= */

static void test_itoa(void) {
    char *s;
    s = ft_itoa(0);        CHECK_STR(s, "0");           free(s);
    s = ft_itoa(1);        CHECK_STR(s, "1");           free(s);
    s = ft_itoa(-1);       CHECK_STR(s, "-1");          free(s);
    s = ft_itoa(42);       CHECK_STR(s, "42");          free(s);
    s = ft_itoa(-42);      CHECK_STR(s, "-42");         free(s);
    s = ft_itoa(INT_MAX);  CHECK_STR(s, "2147483647");  free(s);
    s = ft_itoa(INT_MIN);  CHECK_STR(s, "-2147483648"); free(s);
    s = ft_itoa(100);      CHECK_STR(s, "100");         free(s);
    s = ft_itoa(-100);     CHECK_STR(s, "-100");        free(s);
}

static char strmapi_xform(unsigned int i, char c) {
    return (i % 2 == 0) ? c : (char)(c + 1);
}

static void test_strmapi(void) {
    /* keep even-index chars, +1 odd-index: "abcd" -> "acce" */
    char *s = ft_strmapi("abcd", strmapi_xform);
    CHECK_STR(s, "acce");
    free(s);
    /* empty input must allocate and return "" */
    s = ft_strmapi("", strmapi_xform);
    CHECK(s != NULL);
    if (s) { CHECK_STR(s, ""); free(s); }
}

static void striteri_xform(unsigned int i, char *c) {
    if (i % 2 == 0) *c = (char)(*c + 1);
}

static void test_striteri(void) {
    char buf[] = "abcd";
    ft_striteri(buf, striteri_xform);
    /* +1 even-index: "abcd" -> "bbdd" */
    CHECK_STR(buf, "bbdd");
    /* empty must not crash */
    char empty[] = "";
    ft_striteri(empty, striteri_xform);
    CHECK_STR(empty, "");
}

/* ============= Part 2: put*_fd ============= */

static char *capture_to_pipe(void (*emit)(int)) {
    static char buf[1024];
    int fds[2];
    if (pipe(fds) != 0) return NULL;
    emit(fds[1]);
    close(fds[1]);
    ssize_t total = 0, n;
    while ((n = read(fds[0], buf + total, sizeof(buf) - 1 - (size_t)total)) > 0) {
        total += n;
        if (total >= (ssize_t)sizeof(buf) - 1) break;
    }
    close(fds[0]);
    if (total < 0) total = 0;
    buf[total] = '\0';
    return buf;
}

static char g_emit_char;
static const char *g_emit_str;
static int g_emit_int;

static void emit_putchar(int fd) { ft_putchar_fd(g_emit_char, fd); }
static void emit_putstr(int fd)  { ft_putstr_fd((char *)g_emit_str, fd); }
static void emit_putendl(int fd) { ft_putendl_fd((char *)g_emit_str, fd); }
static void emit_putnbr(int fd)  { ft_putnbr_fd(g_emit_int, fd); }

static void test_putchar_fd(void) {
    g_emit_char = 'X'; CHECK_STR(capture_to_pipe(emit_putchar), "X");
    g_emit_char = '\0'; /* writing '\0' should still produce one byte */
    int fds[2];
    if (pipe(fds) == 0) {
        ft_putchar_fd('\0', fds[1]);
        close(fds[1]);
        char b[2] = {0x42, 0x42};
        ssize_t n = read(fds[0], b, 1);
        close(fds[0]);
        CHECK_INT(n, 1);
        CHECK_INT(b[0], 0);
    }
}

static void test_putstr_fd(void) {
    g_emit_str = "hello";   CHECK_STR(capture_to_pipe(emit_putstr), "hello");
    g_emit_str = "";        CHECK_STR(capture_to_pipe(emit_putstr), "");
    g_emit_str = "42Tokyo"; CHECK_STR(capture_to_pipe(emit_putstr), "42Tokyo");
}

static void test_putendl_fd(void) {
    g_emit_str = "hello"; CHECK_STR(capture_to_pipe(emit_putendl), "hello\n");
    g_emit_str = "";      CHECK_STR(capture_to_pipe(emit_putendl), "\n");
}

static void test_putnbr_fd(void) {
    g_emit_int = 0;       CHECK_STR(capture_to_pipe(emit_putnbr), "0");
    g_emit_int = 1;       CHECK_STR(capture_to_pipe(emit_putnbr), "1");
    g_emit_int = -1;      CHECK_STR(capture_to_pipe(emit_putnbr), "-1");
    g_emit_int = 42;      CHECK_STR(capture_to_pipe(emit_putnbr), "42");
    g_emit_int = -42;     CHECK_STR(capture_to_pipe(emit_putnbr), "-42");
    g_emit_int = INT_MAX; CHECK_STR(capture_to_pipe(emit_putnbr), "2147483647");
    g_emit_int = INT_MIN; CHECK_STR(capture_to_pipe(emit_putnbr), "-2147483648");
    g_emit_int = 100;     CHECK_STR(capture_to_pipe(emit_putnbr), "100");
    g_emit_int = -100;    CHECK_STR(capture_to_pipe(emit_putnbr), "-100");
}

/* ============= Part 3: linked list (bonus only) ============= */

#ifdef LIBFT_BONUS

static int g_iter_count;
static int g_iter_sum;

static void noop_iter(void *p) { (void)p; }
static void iter_count_up(void *p) { (void)p; g_iter_count++; }
static void iter_sum(void *p) { g_iter_sum += *(int *)p; }

static void *map_dup_int_double(void *content) {
    int *r = malloc(sizeof(int));
    if (!r) return NULL;
    *r = *(int *)content * 2;
    return r;
}

static t_list *make_int_list(const int *vals, size_t n) {
    t_list *lst = NULL;
    for (size_t i = 0; i < n; i++) {
        int *p = malloc(sizeof(int));
        if (!p) return lst;
        *p = vals[i];
        ft_lstadd_back(&lst, ft_lstnew(p));
    }
    return lst;
}

static void test_lstnew(void) {
    int *x = malloc(sizeof(int));
    *x = 42;
    t_list *node = ft_lstnew(x);
    CHECK(node != NULL);
    if (node) {
        CHECK(node->content == x);
        CHECK(node->next == NULL);
        ft_lstdelone(node, free);
    }
    /* NULL content must be acceptable (subject doesn't forbid). */
    t_list *n2 = ft_lstnew(NULL);
    CHECK(n2 != NULL);
    if (n2) {
        CHECK(n2->content == NULL);
        CHECK(n2->next == NULL);
        ft_lstdelone(n2, NULL);
        /* del=NULL means: don't free content, but free node. lstdelone
         * must still free the node. valgrind will complain if not. */
    }
}

static void test_lstadd_front(void) {
    t_list *lst = NULL;
    /* into empty list */
    ft_lstadd_front(&lst, ft_lstnew(strdup("b")));
    CHECK(lst != NULL);
    if (lst) CHECK_STR((char *)lst->content, "b");
    /* prepend */
    ft_lstadd_front(&lst, ft_lstnew(strdup("a")));
    CHECK_INT(ft_lstsize(lst), 2);
    if (lst) {
        CHECK_STR((char *)lst->content, "a");
        CHECK(lst->next != NULL);
        if (lst->next) CHECK_STR((char *)lst->next->content, "b");
    }
    ft_lstclear(&lst, free);
    CHECK(lst == NULL);
}

static void test_lstadd_back(void) {
    t_list *lst = NULL;
    ft_lstadd_back(&lst, ft_lstnew(strdup("a")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("b")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("c")));
    CHECK_INT(ft_lstsize(lst), 3);
    if (lst && lst->next && lst->next->next) {
        CHECK_STR((char *)lst->content, "a");
        CHECK_STR((char *)lst->next->content, "b");
        CHECK_STR((char *)lst->next->next->content, "c");
        CHECK(lst->next->next->next == NULL);
    } else {
        FAIL("lstadd_back: list shorter than expected");
    }
    ft_lstclear(&lst, free);
}

static void test_lstsize(void) {
    CHECK_INT(ft_lstsize(NULL), 0);
    int v[] = {1, 2, 3, 4, 5};
    t_list *lst = make_int_list(v, 5);
    CHECK_INT(ft_lstsize(lst), 5);
    ft_lstclear(&lst, free);
    /* single node */
    int *p = malloc(sizeof(int));
    *p = 9;
    t_list *single = ft_lstnew(p);
    CHECK_INT(ft_lstsize(single), 1);
    ft_lstclear(&single, free);
}

static void test_lstlast(void) {
    CHECK(ft_lstlast(NULL) == NULL);
    int v[] = {10, 20, 30};
    t_list *lst = make_int_list(v, 3);
    t_list *last = ft_lstlast(lst);
    CHECK(last != NULL);
    if (last) {
        CHECK_INT(*(int *)last->content, 30);
        CHECK(last->next == NULL);
    }
    ft_lstclear(&lst, free);
    /* single node returns itself */
    int *p = malloc(sizeof(int));
    *p = 7;
    t_list *single = ft_lstnew(p);
    CHECK(ft_lstlast(single) == single);
    ft_lstclear(&single, free);
}

static void test_lstiter(void) {
    int v[] = {1, 2, 3, 4};
    t_list *lst = make_int_list(v, 4);
    g_iter_count = 0;
    g_iter_sum = 0;
    ft_lstiter(lst, iter_count_up);
    CHECK_INT(g_iter_count, 4);
    ft_lstiter(lst, iter_sum);
    CHECK_INT(g_iter_sum, 10);
    /* NULL list must not crash */
    ft_lstiter(NULL, noop_iter);
    ft_lstclear(&lst, free);
}

static void test_lstdelone(void) {
    /* delone must NOT free node->next. */
    int v[] = {1, 2};
    t_list *lst = make_int_list(v, 2);
    t_list *second = lst->next;
    /* detach the head, delete it; tail must be intact */
    lst->next = NULL;
    ft_lstdelone(lst, free);
    CHECK(second != NULL);
    if (second) {
        CHECK_INT(*(int *)second->content, 2);
        CHECK(second->next == NULL);
    }
    ft_lstdelone(second, free);
}

static void test_lstclear(void) {
    int v[] = {1, 2, 3};
    t_list *lst = make_int_list(v, 3);
    ft_lstclear(&lst, free);
    CHECK(lst == NULL);
    /* clearing a NULL list must not crash */
    t_list *empty = NULL;
    ft_lstclear(&empty, free);
    CHECK(empty == NULL);
}

static void test_lstmap(void) {
    int v[] = {1, 2, 3};
    t_list *lst = make_int_list(v, 3);
    t_list *mapped = ft_lstmap(lst, map_dup_int_double, free);
    CHECK(mapped != NULL);
    if (mapped) {
        CHECK_INT(ft_lstsize(mapped), 3);
        CHECK_INT(*(int *)mapped->content, 2);
        if (mapped->next) CHECK_INT(*(int *)mapped->next->content, 4);
        if (mapped->next && mapped->next->next)
            CHECK_INT(*(int *)mapped->next->next->content, 6);
        ft_lstclear(&mapped, free);
    }
    ft_lstclear(&lst, free);
    /* empty input -> empty result */
    t_list *m2 = ft_lstmap(NULL, map_dup_int_double, free);
    CHECK(m2 == NULL);
}

#endif /* LIBFT_BONUS */

/* ============= entry point ============= */

int main(void) {
    /* Part 1 */
    test_ft_isalpha(); test_ft_isdigit(); test_ft_isalnum();
    test_ft_isascii(); test_ft_isprint();
    test_toupper_full(); test_tolower_full();
    test_strlen();
    test_memset();   test_bzero();
    test_memcpy();   test_memmove();
    test_strlcpy();  test_strlcat();
    test_strchr();   test_strrchr();
    test_strncmp();  test_memchr();   test_memcmp();
    test_strnstr();  test_atoi();
    test_calloc();   test_strdup();
    /* Part 2 */
    test_substr();   test_strjoin();   test_strtrim();
    test_split();    test_itoa();
    test_strmapi();  test_striteri();
    test_putchar_fd(); test_putstr_fd();
    test_putendl_fd(); test_putnbr_fd();

#ifdef LIBFT_BONUS
    /* Part 3 */
    test_lstnew();        test_lstadd_front(); test_lstadd_back();
    test_lstsize();       test_lstlast();      test_lstiter();
    test_lstdelone();     test_lstclear();     test_lstmap();
#endif

    if (g_failures > 0) {
        fprintf(stderr, "\n%d behavioural test(s) failed\n", g_failures);
        return 1;
    }
    return 0;
}
