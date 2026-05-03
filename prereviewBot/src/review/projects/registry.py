from __future__ import annotations

from review.projects.base import ProjectSpec
from review.projects.libft import LIBFT

_PROJECTS: dict[str, ProjectSpec] = {}


def register(project: ProjectSpec) -> None:
    if project.name in _PROJECTS:
        raise ValueError(f"project already registered: {project.name}")
    _PROJECTS[project.name] = project


def get(name: str) -> ProjectSpec:
    try:
        return _PROJECTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown project: {name}") from exc


def all_names() -> list[str]:
    return sorted(_PROJECTS.keys())


# Built-in projects are registered at import time.
register(LIBFT)
