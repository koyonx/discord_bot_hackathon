from __future__ import annotations

from review.checks.compile_flags import compile_flags_check
from review.checks.forbidden_externals import forbidden_externals_check
from review.checks.globals import no_globals_check
from review.checks.header_rules import header_rules_check
from review.checks.make_targets import make_targets_check
from review.checks.makefile_rules import makefile_rules_check
from review.checks.no_relink import no_relink_check
from review.checks.norminette import norminette_check
from review.checks.repo_layout import repo_layout_check
from review.checks.required_functions import required_functions_check
from review.checks.tester import libft_smoke_check
from review.projects.base import ProjectSpec

# Function lists are taken verbatim from the v19.2 subject (Chapter IV).
_LIBFT_PART1_LIBC = (
    "ft_isalpha", "ft_isdigit", "ft_isalnum", "ft_isascii", "ft_isprint",
    "ft_strlen", "ft_memset", "ft_bzero", "ft_memcpy", "ft_memmove",
    "ft_strlcpy", "ft_strlcat", "ft_toupper", "ft_tolower",
    "ft_strchr", "ft_strrchr", "ft_strncmp", "ft_memchr", "ft_memcmp",
    "ft_strnstr", "ft_atoi",
)
_LIBFT_PART1_MALLOC = ("ft_calloc", "ft_strdup")
_LIBFT_PART2 = (
    "ft_substr", "ft_strjoin", "ft_strtrim", "ft_split", "ft_itoa",
    "ft_strmapi", "ft_striteri",
    "ft_putchar_fd", "ft_putstr_fd", "ft_putendl_fd", "ft_putnbr_fd",
)
_LIBFT_BONUS = (
    "ft_lstnew", "ft_lstadd_front", "ft_lstsize", "ft_lstlast",
    "ft_lstadd_back", "ft_lstdelone", "ft_lstclear", "ft_lstiter", "ft_lstmap",
)


def _build_libft_checks(project: ProjectSpec, bonus: bool):
    """Order matters: build/parse-only checks run first so that even when
    `make all` fails the user still sees actionable structural feedback."""
    return [
        # Static / textual (run regardless of build success)
        repo_layout_check(project, bonus=bonus),
        makefile_rules_check(project, bonus=bonus),
        header_rules_check(project, bonus=bonus),
        # Source-level
        norminette_check(project, bonus=bonus),
        compile_flags_check(project, bonus=bonus),
        # Build
        make_targets_check(project, bonus=bonus),
        no_relink_check(project, bonus=bonus),
        # Archive analysis (depends on libft.a from `make all`)
        required_functions_check(project, bonus=bonus),
        no_globals_check(project, bonus=bonus),
        forbidden_externals_check(project, bonus=bonus),
        # Runtime
        libft_smoke_check(project, bonus=bonus),
    ]


LIBFT = ProjectSpec(
    name="libft",
    description="42Tokyo libft v19.2 — re-implement a subset of libc.",
    required_make_targets=("all", "clean", "fclean", "re"),
    bonus_make_target="bonus",
    expected_artifacts_mandatory=("libft.a",),
    expected_artifacts_bonus=("libft.a",),
    norminette_targets_mandatory=("ft_*.c", "libft.h"),
    norminette_targets_bonus=("ft_*.c", "*_bonus.c", "libft.h", "*_bonus.h"),
    required_mandatory_functions=tuple(
        _LIBFT_PART1_LIBC + _LIBFT_PART1_MALLOC + _LIBFT_PART2
    ),
    required_bonus_functions=_LIBFT_BONUS,
    # Subject: Part 1 libc reimplementations may not call any external functions;
    # ft_calloc/ft_strdup/Part 2 may use malloc/free/write per their tables.
    # The library as a whole therefore only references these three.
    allowed_external_libc=frozenset({"malloc", "free", "write"}),
    forbidden_header_keywords=("restrict",),
    forbidden_makefile_substrings=("-std=c99", "libtool"),
    required_makefile_substrings=("ar",),
    forbidden_makefile_compilers=("gcc", "clang", "g++", "c++"),
    bonus_typedef_name="t_list",
    check_builder=_build_libft_checks,
)
