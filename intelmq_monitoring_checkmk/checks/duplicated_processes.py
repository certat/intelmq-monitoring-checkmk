"""
Lists all IntelMQ processes and looks for duplications. Any duplicated bot may lead in some cases
to duplication in data and interrupt other checks or workflows
"""

import logging
import subprocess

from ..base import BaseServiceCheck
from ..writer import CheckStatus

logger = logging.getLogger(__name__)


class DuplicatedProcessesCheck(BaseServiceCheck):
    DESCRIPTION = """
Look for duplicated IntelMQ processes. If they are any, they may lead to data duplication (e.g.
when they change data in EventDB) and affect other workflows (e.g. other checks). Any process
duplication is not a part of normal IntelMQ work.

When some duplications are found, please manually kill duplicated process. You could either
kill older process or all duplicated. Regardless of the chosen solution, ensure in the IntelMQ
monitor that the duplicated bot is working, or start when all processes were killed.

Only processes run by intelmq user and with 'intelmq' in the command are analyzed.

This check bases on the previous 'cronjob_intelmq_check_duplicate_processes.sh' script.
"""
    NAME = "Duplicated IntelMQ processes"
    USE_STORAGE = False
    COMMAND = (
        "ps -o start_time,pid,command -U intelmq | grep intelmq | sort | uniq -D -f 2"
    )

    def proceed(self):
        results = subprocess.run(
            self.COMMAND,
            text=True,
            shell=True,
            check=True,
            timeout=3,
            capture_output=True,
        )
        logger.debug("Duplication command returned: %s", results.stdout)

        duplicated = []
        if not results.stdout:
            self.writer.status = CheckStatus.OK
            self.writer.set_short_summary("No duplicated processes found")
        else:
            duplicated = results.stdout.split("\n")
            self.writer.status = CheckStatus.CRITICAL
            self.writer.set_short_summary(
                f"{len(duplicated)} processes has to be reviewed"
            )
            self.writer.add_summary_line("Please review (start_time pid command)")
            self.writer.add_summary_line(results.stdout)
        self.writer.add_metric("duplicated-processes", len(duplicated))
