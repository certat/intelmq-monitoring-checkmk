"""
...
"""

import json
import logging
import subprocess
from time import perf_counter_ns, sleep

from ..base import BaseServiceCheck
from ..config import Config
from ..writer import CheckStatus

logger = logging.getLogger(__name__)


class ScriptExecutionWrapperCheck(BaseServiceCheck, auto_register=False):
    """It wraps the command and monitor the result. Thus, the command is
    executed in the shell mode and not escaped.
    """

    DESCRIPTION = "Wraps execution of an arbitrary command and monitor it's result"
    PREFIX = Config.PREFIX_SCRIPT
    USE_STORAGE = False

    def __init__(
        self,
        config: Config,
        name: str,
        cmd: str,
        valid_for: int,
        retry: int = 1,
        json_metrics: bool = False,
    ) -> None:
        self.NAME = name
        self.valid_for = valid_for
        self.cmd = cmd
        self.retry = retry
        self.json_metrics = json_metrics
        super().__init__(config)
        self.logger = logger.getChild(self.name)
        self.writer.timeout = valid_for
        self._tries = 0

    def _process_json_metrics(self, output: str):
        if not self.json_metrics:
            return

        try:
            data: dict = json.loads(output)
            for metic_name, value in data.items():
                self.writer.add_metric(metic_name, value)
        except json.JSONDecodeError:
            self.logger.warning("Error decoding output as JSON")
            self.writer.add_summary_line(
                "Expected metrics data not found in the output"
            )
            self.writer.status = CheckStatus.WARNING
        except Exception:
            self.logger.exception("Error processing JSON metrics")
            self.writer.add_summary_line("Error processing metrics")
            self.writer.status = CheckStatus.WARNING

    def run(self):
        for self._tries in range(self.retry):
            self.logger.debug("Running command: %s, try: %s", self.cmd, self._tries)
            result = subprocess.run(
                self.cmd, shell=True, capture_output=True, text=True
            )

            stdout = ""
            self.logger.debug(result.args)
            if result.stdout:
                self.logger.debug(result.stdout)
                stdout = result.stdout
            if result.stderr:
                self.logger.error(result.stderr)

            try:
                result.check_returncode()
                self._process_json_metrics(output=stdout)
                return
            except Exception:
                if self._tries == self.retry - 1:
                    raise
                self.logger.warning(
                    "Command failed on try %d of %d, retrying in %d",
                    self._tries,
                    self.retry,
                    self.config.RETRY_SLEEP,
                )
                sleep(self.config.RETRY_SLEEP)

    def proceed(self):
        time_start = perf_counter_ns()

        try:
            self.run()
            self.writer.status = CheckStatus.OK
        except Exception:
            self.writer.status = CheckStatus.CRITICAL
            self.logger.exception("Script execution failed")

        time_end = perf_counter_ns()
        execution_time_ms = int((time_end - time_start) * 10 ** (-6))
        self.logger.info("Execution finished in %d ms", execution_time_ms)
        self.writer.add_metric("execution-time-ms", execution_time_ms)
        self.writer.add_metric("retries", self._tries)
