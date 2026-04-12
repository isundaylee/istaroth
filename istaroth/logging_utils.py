"""Shared logging configuration."""

import logging


def setup_logging(*, level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)-35s %(message)s",
        datefmt="%Y%m%d %H:%M:%S",
    )
