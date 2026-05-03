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
    # External libc functions that the project's source is allowed to depend on.
    allowed_external_symbols: frozenset[str]
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
    # Builder used by Runner to materialise the list of checks for this project.
    check_builder: "CheckBuilder | None" = field(default=None)


# Forward-declared callable type used by Runner.
from collections.abc import Callable  # noqa: E402

CheckBuilder = Callable[["ProjectSpec", bool], list["Check"]]
