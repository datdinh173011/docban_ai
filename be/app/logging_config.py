import logging

from rich.logging import RichHandler


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
        level=logging.INFO,
        force=True,
    )
