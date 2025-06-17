import json
import os
from datetime import timedelta


class Config:
    """
    Config can be modified by adjusting the /etc/intelmq/monitoring.json file.
    For config entries of type int or string, just put the value.
    For timedelta, prepare a dict with arguments passed to the timedelta constructor.

    Some configs can be set as bot's properties, especially:

    monitoring-ignore-no-data - disable check if collector produces data
    monitoring-activity-window-days - overwrite how long period is checked for inactivity
    monitoring-queue-warning - the warning queue size
    monitoring-queue-critical - the critical queue size
    """

    STORAGE_DIR = "/var/lib/intelmq/monitoring-cache/"
    CHECK_MK_SPOOL_DIR = "/var/lib/check_mk_agent/spool/"

    FOOTNOTE = (
        "Check from intelmq-monitoring-checkmk package, see the Github repository"
        " for details: https://github.com/cert/intelmq-monitoring-checkmk"
    )

    # Timeout of CheckMK agent - when the check output is older, will be ignored
    # Assuming running checks every 5 minutes, add some space for delays (2x the period + 0.3)
    DEFAULT_TIMEOUT = 5 * 60 * 2.3

    # With no changes, updates to timelines should be ignored by storage for 14 minutes
    TIMELINE_RATE_LIMIT = timedelta(minutes=14)

    PREFIX_SUMMARY = "intelmq-summary"
    PREFIX_BOT = "intelmq-bot"
    PREFIX_SCRIPT = "intelmq-periodic"

    TIME_WINDOW = timedelta(days=6)
    ERROR_RATE_WINDOW = timedelta(days=2)

    QUEUE_WARNING = 20000
    QUEUE_CRITICAL = 50000

    FAILURES_WARNING = 5  # Temporary
    FAILURES_CRITICAL = 100

    ERROR_RATE_WARNING = 5  # Temporary
    ERROR_RATE_CRITICAL = 50

    # Set this property in bot's config to exclude from checks of inactive collectors.
    # The content should be not empty and will be uses as description of the reason
    INACTIVE_COLLECTOR_IGNORING_KEY = "monitoring-ignore-no-data"
    MONITORING_CONFIG_PREFIX = "monitoring-"

    DEFAULT_LOGS_DIR = "/var/log/intelmq/"

    RETRY_SLEEP = 3  # seconds

    def __str__(self) -> str:
        return ", ".join(
            f'"{attr}": {getattr(self, attr)!r}'
            for attr in dir(self)
            if not attr.startswith("__")
        )

    def __init__(self, config_file: str = "/etc/intelmq/monitoring.json"):
        if not os.path.exists(config_file):
            return

        with open(config_file) as f:
            data = json.load(f)

        for key, value in data.items():
            key: str = key.upper()
            if key.startswith("_"):
                raise ValueError("Overwriting internal fields is not allowed")
            default = getattr(Config, key)
            if isinstance(default, str):
                if not isinstance(value, str):
                    raise ValueError(f"Expected string for key {value}")
                setattr(self, key, value)
            elif isinstance(default, timedelta):
                try:
                    setattr(self, key, timedelta(**value))
                except Exception as exc:
                    raise ValueError(f"Incorrect setting for {key}") from exc
            elif isinstance(default, int):
                if not isinstance(value, int):
                    raise ValueError(f"Expected int for {key}")
                setattr(self, key, value)
            else:
                raise ValueError("Unsupported config type")
