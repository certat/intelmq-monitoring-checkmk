import logging
from abc import ABC, abstractmethod
from time import perf_counter_ns
from typing import List, Type

from intelmq.bin.intelmqctl import IntelMQController
from redis import Redis

from .config import Config
from .helpers import (
    get_intelmq_global_settings,
    get_intelmq_runtime_settings,
    normalize_name,
)
from .storage import Storage
from .writer import CheckMKWriter

logger = logging.getLogger(__name__)


class BaseServiceCheck(ABC):
    """Any subclass is automatically registered as a check to run"""

    # prefix - prefix added for easier grouping in the CheckMK
    PREFIX = Config.PREFIX_SUMMARY
    NAME = None
    DESCRIPTION = ""
    USE_STORAGE = True

    __REGISTERED_SERVICES: List[Type["BaseServiceCheck"]] = list()

    def __init_subclass__(cls, auto_register=True, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if auto_register:
            logger.debug("Registered check %s", cls.__name__)
            BaseServiceCheck.__REGISTERED_SERVICES.append(cls)

    def __init__(self, config: Config) -> None:
        self.config = config
        if self.USE_STORAGE:
            self.storage = Storage(config, self.normalized_name)
        self.writer = CheckMKWriter(config, self.name, description=self.DESCRIPTION)

    @property
    def name(self):
        return f"{self.PREFIX}-{self.NAME}"

    @property
    def normalized_name(self):
        return normalize_name(self.name)

    @staticmethod
    def _get_cached_static_property(name, generator_fn):
        """To avoid repeating preparing resources used by multiple checks,
        cache them on the base class level"""

        if not getattr(BaseServiceCheck, name, None):
            setattr(BaseServiceCheck, name, generator_fn())
        return getattr(BaseServiceCheck, name)

    @property
    def intelmq_global(self):
        return self._get_cached_static_property(
            "_intelmq_global", get_intelmq_global_settings
        )

    @property
    def intelmq_runtime(self) -> dict:
        return self._get_cached_static_property(
            "_intelmq_runtime", get_intelmq_runtime_settings
        )

    @property
    def intelmq_cli(self) -> IntelMQController:
        def _prepare_cli():
            return IntelMQController(interactive=False)

        return self._get_cached_static_property("_intelmq_cli", _prepare_cli)

    @property
    def stat_db(self) -> Redis:
        def _connect():
            return Redis(
                host=self.intelmq_global.get("statistics_host", "127.0.0.1"),
                port=self.intelmq_global.get("statistics_port", 6379),
                db=self.intelmq_global.get("statistics_database", 3),
                password=self.intelmq_global.get("statistics_password"),
                charset="utf-8",
                decode_responses=True,
            )

        return self._get_cached_static_property("_stat_db", _connect)

    @property
    def bots_queues(self):
        def _generate():
            return self.intelmq_cli.list_queues()[1]

        return self._get_cached_static_property("_bots_queues", _generate)

    def get_custom_bot_monitoring_config(self, botid: str, key: str, default=None):
        bot_properties = self.intelmq_runtime.get(botid, {}).get("parameters", {})
        return bot_properties.get(
            f"{self.config.MONITORING_CONFIG_PREFIX}{key}", default
        )

    @abstractmethod
    def proceed(self):
        raise NotImplementedError()

    def check(self):
        logger.info("Running check %s[%s]", self.__class__.__name__, self.name)
        self.proceed()
        if self.USE_STORAGE:
            self.storage.save()
        self.writer.save()

    @classmethod
    def run_all_checks(cls, config: Config, status_writer: CheckMKWriter):
        logger.info("Starting running all checks...")

        status_writer.add_metric("total-checks", len(cls.__REGISTERED_SERVICES))
        failed_checks = 0
        time_start = perf_counter_ns()

        for check in cls.__REGISTERED_SERVICES:
            try:
                check(config).check()
            except Exception:
                logger.exception("Check %s raised an exception", check.__name__)
                failed_checks += 1
                status_writer.add_summary_line(f"Check {check.NAME} failed")
        time_end = perf_counter_ns()
        execution_time_ms = int((time_end - time_start) * 10 ** (-6))

        logger.info("All checks executed in %d ms", execution_time_ms)

        status_writer.add_summary_line(f"Checks executed in {execution_time_ms} ms")
        status_writer.add_metric("failed-checks", failed_checks, critical_level=1)
        status_writer.add_metric("execution-time-ms", execution_time_ms)
        status_writer.set_short_summary(
            "All checks running" if not failed_checks else "Some checks failed"
        )
