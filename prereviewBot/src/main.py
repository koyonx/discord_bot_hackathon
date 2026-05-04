from __future__ import annotations

import asyncio
import logging

from bot import run_bot


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    _configure_logging()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
