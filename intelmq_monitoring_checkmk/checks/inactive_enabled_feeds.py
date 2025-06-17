"""
This checks the number of collector bots, that didn't proceeded any message in the
last TIME_WINDOW period. If it fails, please ensure the listed bots are properly configured
to get feeds data. It may happen, that source changed something or was discontinued.
"""

from datetime import datetime, timedelta

from ..base import BaseServiceCheck
from ..config import Config
from ..helpers import TOTAL_COUNTER_TEMPLATE, is_collector, sum_timeline


class InactiveFeedCheck(BaseServiceCheck):
    DESCRIPTION = f"""
Count the total number of messages processed by enabled collector bots,
and for each check if in given time period (last {Config.TIME_WINDOW}) any message
was processed. If not, then we assume that the feed may not work.

Set "{Config.INACTIVE_COLLECTOR_IGNORING_KEY}" parameter in bot's config to disable
alerts for the given bot.

This check needs to collect data for the given period before producing meaningful results.
"""
    NAME = "Inactive enabled feeds"

    def _get_time_window(self, botid: str):
        cfg_value = self.get_custom_bot_monitoring_config(botid, "activity-window-days")
        if not cfg_value:
            return self.config.TIME_WINDOW
        return timedelta(days=cfg_value)

    def proceed(self):
        enabled_collectors = list(
            filter(
                lambda botid: is_collector(self.intelmq_runtime[botid])
                and self.intelmq_runtime[botid].get("enabled", False) is True,
                self.intelmq_runtime.keys(),
            )
        )

        for collector in enabled_collectors:
            value = 0
            for queue in self.stat_db.keys(TOTAL_COUNTER_TEMPLATE.format(collector)):
                value += int(self.stat_db.get(queue) or 0)
            self.storage.add_timeline_entry(key=collector, value=value)

        # clean old entries
        for key in self.storage.keys():
            period_start = datetime.utcnow() - self._get_time_window(key)
            self.storage.clean_timeline_key(key=key, threshold=period_start)

        inactive = 0
        ignored = 0
        for collector in enabled_collectors:
            ignore_reason = (
                self.intelmq_runtime[collector]
                .get("parameters", {})
                .get(self.config.INACTIVE_COLLECTOR_IGNORING_KEY)
            )
            if ignore_reason:
                self.writer.add_summary_line(
                    f'SKIPPED collector {collector}, reason: "{ignore_reason}"'
                )
                ignored += 1
                continue

            # Data points are expected to be sorted by the collecting time
            total_proceeded = sum_timeline(iter(self.storage[collector]))

            if total_proceeded <= 0:
                inactive += 1
                self.writer.add_summary_line(
                    f"Collector {collector} has 0 processed messages in "
                    f"last {self._get_time_window(collector)}"
                )

        self.writer.add_metric("inactive_feeds", inactive, 1, 10)
        self.writer.add_metric("skipped_during_check", ignored)
        self.writer.set_short_summary(
            "All feeds operational"
            if not inactive
            else f"Found {inactive} feeds with troubles"
        )
