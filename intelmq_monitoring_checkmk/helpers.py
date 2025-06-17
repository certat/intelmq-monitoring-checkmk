import argparse
import logging
from typing import Iterator, Optional

try:
    from intelmq.lib.utils import get_global_settings, get_runtime
except ImportError:  # for the IntelMQ 2 support
    from intelmq import DEFAULTS_CONF_FILE, RUNTIME_CONF_FILE
    from intelmq.lib.utils import load_configuration

    def get_global_settings():
        return load_configuration(DEFAULTS_CONF_FILE)

    def get_runtime():
        return load_configuration(RUNTIME_CONF_FILE)


TOTAL_COUNTER_TEMPLATE = "{}.total.*"


def get_intelmq_global_settings():
    return get_global_settings()


def get_intelmq_runtime_settings():
    return get_runtime()


def normalize_name(name: str):
    return name.lower().replace(" ", "_")[:100]


def sum_timeline(data_iter: Iterator[dict]) -> int:
    # if bot was restarted, IntelMQ resets stats
    # Here look for all restart points and sum

    last_starting_value = next(data_iter, None)
    last_starting_value = last_starting_value["value"] if last_starting_value else None
    if last_starting_value is None:
        return None

    sum_value = 0
    previous_value, value = last_starting_value, 0
    for data_point in data_iter:
        value = data_point["value"]
        if value < previous_value:  # Bot restarted
            sum_value += previous_value - last_starting_value
            last_starting_value = 0
        previous_value = value

    sum_value += previous_value - last_starting_value
    return sum_value


def is_collector(bot_config: dict):
    if "groupname" in bot_config and bot_config["groupname"] == "collectors":
        return True
    if "group" in bot_config and bot_config["group"] == "Collector":
        return True
    return False


def configure_logging(log_level: str, file_path: Optional[str]):
    logging.basicConfig(
        filename=file_path,
        level=log_level.upper(),
        format=f"%(asctime)s {logging.BASIC_FORMAT}",
    )


def prepare_logging_parser(parser: argparse.ArgumentParser, default_dir: str = None):
    log_args = parser.add_argument_group("logging", "Configure logging")
    if not default_dir:
        log_args.add_argument(
            "--log-file",
            action="store",
            type=str,
            default=None,
            help="File to save logs. If not provided, then printing to the console",
        )
    else:
        log_args.add_argument(
            "--log-dir",
            action="store",
            type=str,
            default=default_dir,
            help="Directory for logs to save in",
        )
    log_args.add_argument(
        "--log-level",
        action="store",
        choices=logging._nameToLevel.keys(),
        default="INFO",
    )

    return parser
