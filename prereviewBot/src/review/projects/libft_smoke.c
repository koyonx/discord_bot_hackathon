/* prereviewBot libft smoke test
 *
 * Exercises every function required by the Libft v19.2 subject and flags any
 * deviation from the spec'd behaviour. Compiled and linked against the
 * student's libft.a; run under -fsanitize=address,undefined so that leaks,
 * out-of-bounds accesses, and undefined behaviour fail the run.
 */

#define _GNU_SOURCE

#include "libft.h"

#include <ctype.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

static int g_failures;

#define FAIL(fmt, ...)                                                    \
    do {                                                                  \
        fprintf(stderr, "FAIL %s:%d: " fmt "\n", __FILE__, __LINE__,      \
                ##__VA_ARGS__);                                           \
        g_failures++;                                                     \
    } while (0)

#define CHECK(expr)                                                       \
    do {                                                                  \
        if (!(expr)) FAIL("%s", #expr);                                   \
    } while (0)

#define CHECK_INT(actual, expected)                                       \
    do {                                                                  \
        long _a = (long)(actual);                                         \
        long _e = (long)(expected);                                       \
        if (_a != _e) FAIL("%s -> %ld, expected %ld", #actual, _a, _e);   \
    } while (0)

#define CHECK_STR(actual, expected)                                       \
    do {                                                                  \
        const char *_a = (actual);                                        \
        const char *_e = (expected);                                      \
        if (!_a || !_e || strcmp(_a, _e) != 0)                            \
            FAIL("%s -> \"%s\", expected \"%s\"",                         \
                 #actual, _a ? _a : "(null)", _e ? _e : "(null)");        \
    } while (0)

/* ------------ Part 1: libc reimplementations ------------ */

static void test_isalpha(void) {
    CHECK_INT(ft_isalpha('a'), 1);
    CHECK_INT(ft_isalpha('Z'), 1);
    CHECK_INT(ft_isalpha('m'), 1);
    CHECK_INT(ft_isalpha('0'), 0);
    CHECK_INT(ft_isalpha(' '), 0);
    CHECK_INT(ft_isalpha(0), 0);
    CHECK_INT(ft_isalpha(127), 0);
    CHECK_INT(ft_isalpha('@'), 0);
}

static void test_isdigit(void) {
    CHECK_INT(ft_isdigit('0'), 1);
    CHECK_INT(ft_isdigit('9'), 1);
    CHECK_INT(ft_isdigit('a'), 0);
    CHECK_INT(ft_isdigit('/'), 0);
    CHECK_INT(ft_isdigit(':'), 0);
}

static void test_isalnum(void) {
    CHECK_INT(ft_isalnum('a'), 1);
    CHECK_INT(ft_isalnum('Z'), 1);
    CHECK_INT(ft_isalnum('5'), 1);
    CHECK_INT(ft_isalnum(' '), 0);
    CHECK_INT(ft_isalnum('!'), 0);
}

static void test_isascii(void) {
    CHECK_INT(ft_isascii(0), 1);
    CHECK_INT(ft_isascii(127), 1);
    CHECK_INT(ft_isascii(128), 0);
    CHECK_INT(ft_isascii(-1), 0);
    CHECK_INT(ft_isascii(255), 0);
}

static void test_isprint(void) {
    CHECK_INT(ft_isprint(' '), 1);
    CHECK_INT(ft_isprint('~'), 1);
    CHECK_INT(ft_isprint(126), 1);
    CHECK_INT(ft_isprint(31), 0);
    CHECK_INT(ft_isprint(127), 0);
    CHECK_INT(ft_isprint('\t'), 0);
}

static void test_strlen(void) {
    CHECK_INT(ft_strlen(""), 0);
    CHECK_INT(ft_strlen("a"), 1);
    CHECK_INT(ft_strlen("hello"), 5);
    CHECK_INT(ft_strlen("42Tokyo"), 7);
}

static void test_memset(void) {
    char buf[8];
    memset(buf, 'X', sizeof(buf));
    void *r = ft_memset(buf, 'A', 4);
    CHECK(r == buf);
    CHECK_INT(buf[0], 'A');
    CHECK_INT(buf[3], 'A');
    CHECK_INT(buf[4], 'X');
    /* n=0 must leave buffer untouched */
    char b2[2] = {1, 2};
    ft_memset(b2, 'Z', 0);
    CHECK_INT(b2[0], 1);
    CHECK_INT(b2[1], 2);
}

static void test_bzero(void) {
    char buf[5] = {1, 2, 3, 4, 5};
    ft_bzero(buf, 3);
    CHECK_INT(buf[0], 0);
    CHECK_INT(buf[1], 0);
    CHECK_INT(buf[2], 0);
    CHECK_INT(buf[3], 4);
    CHECK_INT(buf[4], 5);
}

static void test_memcpy(void) {
    char dst[8] = {0};
    const char *src = "hello";
    void *r = ft_memcpy(dst, src, 6); /* include terminator */
    CHECK(r == dst);
    CHECK_STR(dst, "hello");
    /* n=0 */
    char d2[3] = {'a', 'b', 'c'};
    ft_memcpy(d2, "ZZ", 0);
    CHECK_INT(d2[0], 'a');
}

static void test_memmove(void) {
    char buf[16] = "hello world";
    /* forward overlap: copy [0..5) into [2..7) */
    ft_memmove(buf + 2, buf, 5);
    CHECK_INT(memcmp(buf, "hehello", 7), 0);
    /* backward overlap */
    char buf2[16] = "hello world";
    ft_memmove(buf2, buf2 + 6, 5);
    CHECK_INT(memcmp(buf2, "world", 5), 0);
}

static void test_strlcpy(void) {
    char dst[8];
    /* truncation */
    memset(dst, 'X', sizeof(dst));
    CHECK_INT(ft_strlcpy(dst, "abcdefgh", 4), 8);
    CHECK_STR(dst, "abc");
    /* exact fit */
    CHECK_INT(ft_strlcpy(dst, "abc", 4), 3);
    CHECK_STR(dst, "abc");
    /* size 0 must not write */
    char d2[2] = {'Y', 'Y'};
    CHECK_INT(ft_strlcpy(d2, "X", 0), 1);
    CHECK_INT(d2[0], 'Y');
}

static void test_strlcat(void) {
    char dst[16] = "ab";
    CHECK_INT(ft_strlcat(dst, "cd", sizeof(dst)), 4);
    CHECK_STR(dst, "abcd");
    /* truncation */
    char d2[5] = "ab";
    CHECK_INT(ft_strlcat(d2, "cdef", 5), 6);
    CHECK_STR(d2, "abcd");
    /* size <= dlen: must return size + slen */
    char d3[4] = "abc";
    CHECK_INT(ft_strlcat(d3, "xy", 2), 4);
}

static void test_toupper_tolower(void) {
    CHECK_INT(ft_toupper('a'), 'A');
    CHECK_INT(ft_toupper('Z'), 'Z');
    CHECK_INT(ft_toupper('1'), '1');
    CHECK_INT(ft_tolower('A'), 'a');
    CHECK_INT(ft_tolower('z'), 'z');
    CHECK_INT(ft_tolower('5'), '5');
}

static void test_strchr(void) {
    const char *s = "hello";
    CHECK(ft_strchr(s, 'h') == s);
    CHECK(ft_strchr(s, 'l') == s + 2);
    CHECK(ft_strchr(s, 'z') == NULL);
    /* '\0' must point to terminator */
    CHECK(ft_strchr(s, '\0') == s + 5);
}

static void test_strrchr(void) {
    const char *s = "hello";
    CHECK(ft_strrchr(s, 'l') == s + 3);
    CHECK(ft_strrchr(s, 'h') == s);
    CHECK(ft_strrchr(s, 'z') == NULL);
    CHECK(ft_strrchr(s, '\0') == s + 5);
}

static void test_strncmp(void) {
    CHECK_INT(ft_strncmp("abc", "abc", 3), 0);
    CHECK(ft_strncmp("abc", "abd", 3) < 0);
    CHECK(ft_strncmp("abd", "abc", 3) > 0);
    CHECK_INT(ft_strncmp("abc", "abd", 2), 0);
    CHECK_INT(ft_strncmp("", "", 5), 0);
    CHECK_INT(ft_strncmp("abc", "abcd", 0), 0);
}

static void test_memchr(void) {
    const char *s = "hello";
    CHECK(ft_memchr(s, 'l', 5) == s + 2);
    CHECK(ft_memchr(s, 'z', 5) == NULL);
    CHECK(ft_memchr(s, 'l', 2) == NULL);
    CHECK(ft_memchr(s, 'h', 0) == NULL);
}

static void test_memcmp(void) {
    CHECK_INT(ft_memcmp("abc", "abc", 3), 0);
    CHECK(ft_memcmp("abc", "abd", 3) < 0);
    CHECK(ft_memcmp("abd", "abc", 3) > 0);
    CHECK_INT(ft_memcmp("ab", "ac", 0), 0);
}

static void test_strnstr(void) {
    const char *hay = "the quick brown fox";
    CHECK(ft_strnstr(hay, "quick", 19) == hay + 4);
    CHECK(ft_strnstr(hay, "quick", 8) == NULL);
    CHECK(ft_strnstr(hay, "", 5) == hay);
    CHECK(ft_strnstr(hay, "xyz", 19) == NULL);
}

static void test_atoi(void) {
    CHECK_INT(ft_atoi("0"), 0);
    CHECK_INT(ft_atoi("42"), 42);
    CHECK_INT(ft_atoi("  -42"), -42);
    CHECK_INT(ft_atoi("\t\n\v\f\r +123abc"), 123);
    CHECK_INT(ft_atoi("--1"), 0);
    CHECK_INT(ft_atoi(""), 0);
}

static void test_calloc(void) {
    int *p = ft_calloc(4, sizeof(int));
    CHECK(p != NULL);
    if (p) {
        for (int i = 0; i < 4; i++) CHECK_INT(p[i], 0);
        free(p);
    }
    /* calloc(0,0) must return a unique freeable pointer per subject. */
    void *z = ft_calloc(0, 0);
    CHECK(z != NULL);
    free(z);
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
}

/* ------------ Part 2: additional functions ------------ */

static void test_substr(void) {
    char *s = ft_substr("hello world", 6, 5);
    CHECK_STR(s, "world");
    free(s);
    s = ft_substr("hello", 10, 5);
    CHECK(s != NULL);
    CHECK_STR(s, "");
    free(s);
    s = ft_substr("hello", 0, 100);
    CHECK_STR(s, "hello");
    free(s);
}

static void test_strjoin(void) {
    char *s = ft_strjoin("foo", "bar");
    CHECK_STR(s, "foobar");
    free(s);
    s = ft_strjoin("", "x");
    CHECK_STR(s, "x");
    free(s);
    s = ft_strjoin("y", "");
    CHECK_STR(s, "y");
    free(s);
}

static void test_strtrim(void) {
    char *s = ft_strtrim("  hello  ", " ");
    CHECK_STR(s, "hello");
    free(s);
    s = ft_strtrim("xxhelloxx", "x");
    CHECK_STR(s, "hello");
    free(s);
    s = ft_strtrim("hello", "xyz");
    CHECK_STR(s, "hello");
    free(s);
    s = ft_strtrim("xxxx", "x");
    CHECK_STR(s, "");
    free(s);
}

static void test_split(void) {
    char **parts = ft_split("hello world foo", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "hello");
        CHECK_STR(parts[1], "world");
        CHECK_STR(parts[2], "foo");
        CHECK(parts[3] == NULL);
        for (int i = 0; parts[i]; i++) free(parts[i]);
        free(parts);
    }
    parts = ft_split("   leading and trailing   ", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK_STR(parts[0], "leading");
        CHECK_STR(parts[1], "and");
        CHECK_STR(parts[2], "trailing");
        CHECK(parts[3] == NULL);
        for (int i = 0; parts[i]; i++) free(parts[i]);
        free(parts);
    }
    parts = ft_split("", ' ');
    CHECK(parts != NULL);
    if (parts) {
        CHECK(parts[0] == NULL);
        free(parts);
    }
}

static void test_itoa(void) {
    char *s;
    s = ft_itoa(0);        CHECK_STR(s, "0");           free(s);
    s = ft_itoa(42);       CHECK_STR(s, "42");          free(s);
    s = ft_itoa(-42);      CHECK_STR(s, "-42");         free(s);
    s = ft_itoa(INT_MAX);  CHECK_STR(s, "2147483647");  free(s);
    s = ft_itoa(INT_MIN);  CHECK_STR(s, "-2147483648"); free(s);
}

static char strmapi_xform(unsigned int i, char c) {
    return (i % 2 == 0) ? c : (char)(c + 1);
}

static void test_strmapi(void) {
    /* xform keeps even-index chars and increments odd-index chars:
     * "abcd" -> 'a', 'b'+1='c', 'c', 'd'+1='e' -> "acce". */
    char *s = ft_strmapi("abcd", strmapi_xform);
    CHECK_STR(s, "acce");
    free(s);
}

static void striteri_xform(unsigned int i, char *c) {
    if (i % 2 == 0) *c = (char)(*c + 1);
}

static void test_striteri(void) {
    char buf[] = "abcd";
    ft_striteri(buf, striteri_xform);
    /* i=0 a+1=b, i=1 keep b, i=2 c+1=d, i=3 keep d */
    CHECK_STR(buf, "bbdd");
}

/* Helpers for fd output tests. */
static char *capture_to_pipe(void (*emit)(int)) {
    static char buf[1024];
    int fds[2];
    if (pipe(fds) != 0) return NULL;
    emit(fds[1]);
    close(fds[1]);
    ssize_t total = 0;
    ssize_t n;
    while ((n = read(fds[0], buf + total,
                     (ssize_t)sizeof(buf) - 1 - total)) > 0) {
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
    g_emit_char = 'X';
    CHECK_STR(capture_to_pipe(emit_putchar), "X");
}

static void test_putstr_fd(void) {
    g_emit_str = "hello";
    CHECK_STR(capture_to_pipe(emit_putstr), "hello");
}

static void test_putendl_fd(void) {
    g_emit_str = "hello";
    CHECK_STR(capture_to_pipe(emit_putendl), "hello\n");
}

static void test_putnbr_fd(void) {
    g_emit_int = 42;          CHECK_STR(capture_to_pipe(emit_putnbr), "42");
    g_emit_int = -42;         CHECK_STR(capture_to_pipe(emit_putnbr), "-42");
    g_emit_int = 0;           CHECK_STR(capture_to_pipe(emit_putnbr), "0");
    g_emit_int = INT_MAX;     CHECK_STR(capture_to_pipe(emit_putnbr), "2147483647");
    g_emit_int = INT_MIN;     CHECK_STR(capture_to_pipe(emit_putnbr), "-2147483648");
}

/* ------------ Part 3: linked list (bonus only) ------------ */

#ifdef LIBFT_BONUS

static void noop_del(void *p) { free(p); }
static void noop_iter(void *p) { (void)p; }

static void test_lstnew(void) {
    int *x = malloc(sizeof(int));
    *x = 42;
    t_list *node = ft_lstnew(x);
    CHECK(node != NULL);
    if (node) {
        CHECK(node->content == x);
        CHECK(node->next == NULL);
        ft_lstdelone(node, noop_del);
    }
}

static void test_lstadd_front(void) {
    t_list *lst = NULL;
    ft_lstadd_front(&lst, ft_lstnew(strdup("b")));
    ft_lstadd_front(&lst, ft_lstnew(strdup("a")));
    CHECK_INT(ft_lstsize(lst), 2);
    CHECK_STR((char *)lst->content, "a");
    CHECK_STR((char *)lst->next->content, "b");
    ft_lstclear(&lst, free);
    CHECK(lst == NULL);
}

static void test_lstsize_last(void) {
    t_list *lst = NULL;
    CHECK_INT(ft_lstsize(lst), 0);
    ft_lstadd_back(&lst, ft_lstnew(strdup("a")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("b")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("c")));
    CHECK_INT(ft_lstsize(lst), 3);
    t_list *last = ft_lstlast(lst);
    CHECK(last != NULL);
    if (last) CHECK_STR((char *)last->content, "c");
    ft_lstclear(&lst, free);
}

static int g_iter_count;
static void iter_count(void *p) { (void)p; g_iter_count++; }

static void test_lstiter(void) {
    t_list *lst = NULL;
    ft_lstadd_back(&lst, ft_lstnew(strdup("x")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("y")));
    g_iter_count = 0;
    ft_lstiter(lst, iter_count);
    CHECK_INT(g_iter_count, 2);
    ft_lstclear(&lst, free);
    /* Allow a NULL list to be iterated without crash. */
    ft_lstiter(NULL, noop_iter);
}

static void *map_dup_upper(void *content) {
    const char *s = content;
    size_t n = strlen(s);
    char *r = malloc(n + 1);
    if (!r) return NULL;
    for (size_t i = 0; i < n; i++) r[i] = (char)toupper((unsigned char)s[i]);
    r[n] = '\0';
    return r;
}

static void test_lstmap(void) {
    t_list *lst = NULL;
    ft_lstadd_back(&lst, ft_lstnew(strdup("hello")));
    ft_lstadd_back(&lst, ft_lstnew(strdup("world")));
    t_list *mapped = ft_lstmap(lst, map_dup_upper, free);
    CHECK(mapped != NULL);
    if (mapped) {
        CHECK_STR((char *)mapped->content, "HELLO");
        CHECK(mapped->next != NULL);
        if (mapped->next) CHECK_STR((char *)mapped->next->content, "WORLD");
        ft_lstclear(&mapped, free);
    }
    ft_lstclear(&lst, free);
}

#endif /* LIBFT_BONUS */

/* ------------ entry point ------------ */

int main(void) {
    /* Part 1 */
    test_isalpha();    test_isdigit();    test_isalnum();
    test_isascii();    test_isprint();
    test_strlen();     test_memset();     test_bzero();
    test_memcpy();     test_memmove();
    test_strlcpy();    test_strlcat();
    test_toupper_tolower();
    test_strchr();     test_strrchr();
    test_strncmp();    test_memchr();     test_memcmp();
    test_strnstr();    test_atoi();
    test_calloc();     test_strdup();
    /* Part 2 */
    test_substr();     test_strjoin();
    test_strtrim();    test_split();
    test_itoa();       test_strmapi();    test_striteri();
    test_putchar_fd(); test_putstr_fd();
    test_putendl_fd(); test_putnbr_fd();

#ifdef LIBFT_BONUS
    /* Part 3 */
    test_lstnew();
    test_lstadd_front();
    test_lstsize_last();
    test_lstiter();
    test_lstmap();
#endif

    if (g_failures > 0) {
        fprintf(stderr, "\n%d behavioural test(s) failed\n", g_failures);
        return 1;
    }
    return 0;
}
