from __future__ import annotations

from review.checks.compile_flags import compile_flags_check
from review.checks.make_targets import make_targets_check
from review.checks.norminette import norminette_check
from review.checks.tester import smoke_tester_check
from review.projects.base import ProjectSpec


def _build_libft_checks(project: ProjectSpec, bonus: bool):
    return [
        norminette_check(project, bonus=bonus),
        make_targets_check(project, bonus=bonus),
        compile_flags_check(project, bonus=bonus),
        smoke_tester_check(project, bonus=bonus),
    ]


LIBFT = ProjectSpec(
    name="libft",
    description="42Tokyo libft — re-implement a subset of libc.",
    required_make_targets=("all", "clean", "fclean", "re"),
    bonus_make_target="bonus",
    expected_artifacts_mandatory=("libft.a",),
    expected_artifacts_bonus=("libft.a",),
    norminette_targets_mandatory=("ft_*.c", "libft.h"),
    norminette_targets_bonus=("ft_*.c", "*_bonus.c", "libft.h"),
    check_builder=_build_libft_checks,
)
