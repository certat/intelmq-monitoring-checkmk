"""Wraps any command to monitor it's execution"""

import argparse
import logging
from pathlib import Path
from typing import Iterable, Tuple

from . import __version__
from .checks.script_wrapper import ScriptExecutionWrapperCheck
from .config import Config
from .helpers import configure_logging, prepare_logging_parser
from .writer import CheckStatus

logger = logging.getLogger(__name__)


def parse_arguments(config: Config) -> Tuple[argparse.Namespace, Iterable[str]]:
    parser = argparse.ArgumentParser()
    prepare_logging_parser(parser, config.DEFAULT_LOGS_DIR)
    parser.add_argument(
        "--valid-for",
        type=int,
        default=900,
        help="How long the reported status should be considered as valid by the monitoring",
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Name of the monitoring check",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=1,
        help=(
            "The wrapper will try to execute up to given number of times. "
            "If greater than 1, this means retries"
        ),
    )
    parser.add_argument(
        "--json-metrics",
        default=False,
        action="store_true",
        help="Treat command output as JSON and read metrics from it",
    )

    args, cmd = parser.parse_known_args()
    if len(cmd) == 0 or cmd[0] != "--":
        raise ValueError("You need to specify the command after --")
    return args, " ".join(cmd[1:])


def _get_log_file(log_dir: str, name: str, prefix: str):
    return Path(log_dir) / f"{prefix}-{name}.log"


def run(
    config: Config,
    name: str,
    cmd: str,
    valid_for: int,
    retry: int = 1,
    json_metrics: bool = False,
):
    check = ScriptExecutionWrapperCheck(
        config=config,
        name=name,
        cmd=cmd,
        valid_for=valid_for,
        retry=retry,
        json_metrics=json_metrics,
    )
    check.check()

    if check.writer.status != CheckStatus.OK:
        return 1
    return 0


def main():
    config = Config()
    args, cmd = parse_arguments(config)
    log_file = _get_log_file(args.log_dir, args.name, config.PREFIX_SCRIPT)
    configure_logging(args.log_level, log_file)

    logger.info("Starting intelmq-monitor %s", __version__)
    logger.debug("Config: %s, args: %s, cmd: %s", config, vars(args), cmd)

    exit(run(config, args.name, cmd, args.valid_for, args.retry, args.json_metrics))


if __name__ == "__main__":
    main()
