from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from review.check import Check


@dataclass(frozen=True)
class ProjectSpec:
    """Static description of a 42Tokyo project to be reviewed.

    Adding a new project (e.g. ft_printf, get_next_line) is done by:
      1. Defining a new ProjectSpec instance.
      2. Building the list of Checks for it (usually reusing the generic
         checks under review/checks/ with project-specific config).
      3. Registering it via review.projects.registry.register().
    """

    name: str
    description: str
    # Make targets that must exist and succeed for the mandatory part.
    required_make_targets: tuple[str, ...]
    # Make target for the bonus part. None if the project has no bonus.
    bonus_make_target: str | None
    # Files expected to exist after `make` (relative to repo root).
    expected_artifacts_mandatory: tuple[str, ...]
    expected_artifacts_bonus: tuple[str, ...]
    # Glob patterns of source files to feed to norminette (relative to repo root).
    norminette_targets_mandatory: tuple[str, ...]
    norminette_targets_bonus: tuple[str, ...]
    # Compiler flags expected to compile cleanly with.
    required_compile_flags: tuple[str, ...] = ("-Wall", "-Wextra", "-Werror")
    # ft_* functions that must be defined in the produced archive.
    required_mandatory_functions: tuple[str, ...] = ()
    required_bonus_functions: tuple[str, ...] = ()
    # External libc symbols the library is allowed to reference. Anything
    # outside this set (and outside compiler/linker internals) is forbidden.
    allowed_external_libc: frozenset[str] = frozenset()
    # Identifiers that must NOT appear in the project's public header(s).
    forbidden_header_keywords: tuple[str, ...] = ()
    # Substrings that must NOT appear in the Makefile (after stripping comments).
    forbidden_makefile_substrings: tuple[str, ...] = ()
    # Substrings that MUST appear in the Makefile (after stripping comments).
    required_makefile_substrings: tuple[str, ...] = ()
    # Compiler binaries that must NOT appear as command invocations in the Makefile.
    forbidden_makefile_compilers: tuple[str, ...] = ()
    # Typedef name expected in the public header when bonus is enabled (e.g. "t_list").
    bonus_typedef_name: str | None = None
    # README rules.
    readme_required_sections: tuple[str, ...] = ()
    readme_first_line_pattern: str | None = None
    # Builder used by Runner to materialise the list of checks for this project.
    check_builder: "CheckBuilder | None" = field(default=None)


# Forward-declared callable type used by Runner.
from collections.abc import Callable  # noqa: E402

CheckBuilder = Callable[["ProjectSpec", bool], list["Check"]]
