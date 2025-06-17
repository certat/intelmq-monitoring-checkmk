import argparse
import logging

from . import __version__
from .base import BaseServiceCheck

# Checks' modules have to be imported to be registered
from .checks import bot_status  # noqa
from .checks import duplicated_processes  # noqa
from .checks import inactive_enabled_feeds  # noqa
from .config import Config
from .helpers import configure_logging, prepare_logging_parser
from .writer import CheckMKWriter

logger = logging.getLogger(__name__)


def prepare_parser():
    parser = argparse.ArgumentParser()
    parser = prepare_logging_parser(parser)
    return parser


def main():
    parser = prepare_parser()
    args = parser.parse_args()
    configure_logging(args.log_level, args.log_file)
    logger.info("Starting intelmq-monitor %s", __version__)

    config = Config()
    logger.debug("Config: {%s}", config)
    checks_status_writer = CheckMKWriter(
        config, f"{config.PREFIX_SUMMARY}-running-checks", "All checks are working"
    )

    BaseServiceCheck.run_all_checks(config, checks_status_writer)

    checks_status_writer.add_summary_line(f"Check package version: {__version__}")
    checks_status_writer.save()

    logger.info("Execution of intelmq-monitor finished")


if __name__ == "__main__":
    main()
