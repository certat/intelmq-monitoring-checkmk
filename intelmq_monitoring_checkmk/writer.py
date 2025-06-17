import itertools
import logging
import string
from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum
from time import perf_counter_ns
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)

ALLOWED_HOST_CHARS = string.ascii_letters + string.digits + ".-"


class CheckStatus(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


@dataclass
class CounterMetric:
    value: int = 0
    warning_level: int = None
    critical_level: int = None


class CheckMKWriter(AbstractContextManager):
    def __init__(
        self,
        config: Config,
        service_name: str,
        description: str = "",
        timeout: int = None,
        piggyback_host: str = None,
    ) -> None:
        """Write results in the CheckMK format for the agent

        service_name - name of the check
        description - additional comment to write at the down of the summary,
                      visible in the result details
        timeout - how long the results are valid (to ignore old results if
                  check didn't run, should be adjusted to the run interval)
        piggyback_host - if results should utilize piggyback mechanism,
                         here should be the target host name.
                         See: https://docs.checkmk.com/2.2.0/en/piggyback.html
        """
        self.timeout = timeout if timeout is not None else config.DEFAULT_TIMEOUT
        self._config = config
        self._metrics = []
        self._counters = defaultdict(CounterMetric)
        self._summary_lines = []
        self._service_name = service_name
        self._piggyback = piggyback_host
        if self._piggyback:
            if any(c not in ALLOWED_HOST_CHARS for c in self._piggyback):
                logger.error(
                    "Not allowed chars in the piggyback hostname: %s", self._piggyback
                )
                raise ValueError("Not allowed chars in the piggyback hostname!")
        # Looks like CheckMK cannot handle empty first summary line
        self._short_summary = f"Results of {service_name} check"
        self._description = description
        self._status = None

        # for context manager only
        self._execution_start = None

    @property
    def _file_name(self) -> str:
        service = self._service_name
        if self._piggyback:
            service = f"{self._service_name}_{self._piggyback}"
        return f"{int(self.timeout)}_{self._normalize_name(service)}.txt"

    def add_metric(
        self,
        name: str,
        value: float,
        warn_level: int = None,
        critical_level: int = None,
    ):
        # TODO: objects, fixing metric names etc.
        # TODO 2: count metrics

        metric = f"{name}={value:.2f};{warn_level or ''};{critical_level or ''}"

        logger.debug("New metric: %s", metric)
        self._metrics.append(metric)

    def increment_counter(self, name: str, warning: int = None, critical: int = None):
        counter = self._counters[name]
        counter.value += 1
        if warning:
            counter.warning_level = warning
        if critical:
            counter.critical_level = critical

    def add_summary_line(self, line: str):
        """Additional summary lines, listed in the check detailed results."""
        self._summary_lines.append(line.replace("\n", "\\n"))

    def set_short_summary(self, summary):
        """First line of the summary, visible in the CheckMK listings"""
        self._short_summary = summary

    def save(self):
        logger.debug(
            "Saving file %s/%s", self._config.CHECK_MK_SPOOL_DIR, self._file_name
        )
        for name, counter in self._counters.items():
            self.add_metric(
                name, counter.value, counter.warning_level, counter.critical_level
            )

        with open(f"{self._config.CHECK_MK_SPOOL_DIR}/{self._file_name}", "w+") as f:
            if self._piggyback:
                f.write(f"<<<<{self._piggyback}>>>>\n")
            f.write("<<<local>>>\n")
            summary = "\\n".join(
                itertools.chain(
                    # Dynamic summary produced by checks
                    [self._short_summary],
                    self._summary_lines,
                    # Static description to help understand results
                    [
                        "",
                        "#" * 10,
                        *self._description.split("\n"),
                        "#" * 10,
                        self._config.FOOTNOTE,
                        "",
                    ],
                )
            )
            f.write(
                f'{self.status_char} "{self._service_name}" '
                f"{'|'.join(self._metrics) or '-'} {summary}\n"
            )
            if self._piggyback:
                f.write("<<<<>>>>\n")

    @property
    def status(self) -> Optional[CheckStatus]:
        return self._status

    @status.setter
    def status(self, status: CheckStatus):
        # Do not allow downgrading the status
        # and let CRITICAL be the most important status
        if self._status is None:
            self._status = status
        elif status == CheckStatus.CRITICAL or self._status == CheckStatus.CRITICAL:
            self._status = CheckStatus.CRITICAL
        elif self._status.value < status.value:
            self._status = status

    @property
    def status_char(self) -> str:
        if not self.status:
            return "P" if self._metrics else "0"
        return str(self.status.value)

    @staticmethod
    def _normalize_name(name: str):
        return name.lower().replace(" ", "_")[:100]

    def __enter__(self):
        self._execution_start = perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        time_end = perf_counter_ns()
        execution_time_ms = int((time_end - self._execution_start) * 10 ** (-6))
        self.add_metric("execution-time-ms", execution_time_ms)
        if exc_value and exc_type is not SystemExit:
            self.status = CheckStatus.CRITICAL
            self.add_summary_line(f"Execution failed unexpectedly: {exc_value}")
        self.save()
        return super().__exit__(exc_type, exc_value, traceback)
