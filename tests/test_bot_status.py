from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from intelmq_monitoring_checkmk.checks.bot_status import BotStatusCheck
from intelmq_monitoring_checkmk.writer import CheckStatus


@pytest.fixture
def bot_status_check(config):
    return BotStatusCheck(config, "test-bot")


def test_bot_status_creates_service_name_with_bot_id(bot_status_check):
    assert bot_status_check.name == "intelmq-bot-test-bot"


def test_check_bot_not_running_checks_for_disabled(
    bot_status_check, get_check_results, runtime
):
    # For disabled bots, generate an OK service check to keep them in monitoring services
    runtime["test-bot"] = {"groupname": "collectors", "enabled": False}

    bot_status_check.check()

    results = get_check_results(bot_status_check)

    assert results.startswith(
        '0 "intelmq-bot-test-bot" - Bot is disabled\\n\\n##########'
    )


def test_check_bot_status_all_failing_checks_reported(
    bot_status_check, cli_mock, get_check_results, fake_stats, runtime, bot_queues
):
    # _check_bot_state
    cli_mock.bot_status.return_value = 1, "stopped"
    # _check_collector_processed_data
    runtime["test-bot"] = {"groupname": "collectors", "enabled": True}
    fake_stats["test-bot.total._default"] = "0"
    # queue sizes
    bot_queues["test-bot"] = {
        "source_queue": ("test-bot-input", 560),
        "internal_queue": 465,
        "destination_queues": [("dest-1", 56)],
    }

    bot_status_check.check()

    results = get_check_results(bot_status_check)

    # _check_bot_state
    assert "FAIL: Bot in state stopped" in results
    # _check_collector_processed_data
    assert "FAIL: Collector processed no data in last 2 days" in results

    # non-failing stats are reported
    assert "today-produced=" in results
    assert "today-succeeded=" in results
    assert "today-failures=" in results

    assert "input-queue=" in results
    assert "internal-queue=" in results
    assert "destination-dest-1=" in results

    assert "period-error-percentage=" in results


@freeze_time("2023-03-08T12:00:01")
def test_stat_queues_are_cached_and_cleaned(bot_status_check, fake_stats):
    fake_stats["test-bot.total._default"] = "5"
    fake_stats["test-bot.total.path"] = "2"
    fake_stats["test-bot.stats.success"] = "6"
    fake_stats["test-bot.stats.failure"] = "2"

    bot_status_check.storage["total-processed-timeline"] = [
        {"time": "2023-03-06T12:00:00", "value": 5},
        {"time": "2023-03-07T12:00:00", "value": 6},
    ]
    bot_status_check.storage["successes-timeline"] = [
        {"time": "2023-03-06T12:00:00", "value": 2},
        {"time": "2023-03-07T12:00:00", "value": 4},
    ]
    bot_status_check.storage["failures-timeline"] = [
        {"time": "2023-03-06T12:00:00", "value": 0},
        {"time": "2023-03-07T12:00:00", "value": 1},
    ]

    bot_status_check._update_stat_queues_cache()

    assert bot_status_check.storage["total-processed-timeline"] == [
        {"time": "2023-03-07T12:00:00", "value": 6},
        {"time": "2023-03-08T12:00:01", "value": 7},
    ]
    assert bot_status_check.storage["successes-timeline"] == [
        {"time": "2023-03-07T12:00:00", "value": 4},
        {"time": "2023-03-08T12:00:01", "value": 6},
    ]
    assert bot_status_check.storage["failures-timeline"] == [
        {"time": "2023-03-07T12:00:00", "value": 1},
        {"time": "2023-03-08T12:00:01", "value": 2},
    ]


def test_check_bot_state_success(bot_status_check, cli_mock):
    cli_mock.bot_status.return_value = 0, "running"

    bot_status_check._check_bot_state()

    cli_mock.bot_status.assert_called_once_with("test-bot")
    assert bot_status_check.writer.status is None
    assert "OK: Bot in state running" in bot_status_check.writer._summary_lines


def test_check_bot_state_fail(bot_status_check, cli_mock):
    cli_mock.bot_status.return_value = 1, "stopped"

    bot_status_check._check_bot_state()

    cli_mock.bot_status.assert_called_once_with("test-bot")
    assert bot_status_check.writer.status == CheckStatus.CRITICAL
    assert "FAIL: Bot in state stopped" in bot_status_check.writer._summary_lines


def test_check_collector_proceeds_data_success(bot_status_check, runtime):
    runtime["test-bot"] = {"groupname": "collectors", "enabled": True}
    # this check just uses cache updated by separated method
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 3},
        {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 6},
    ]

    bot_status_check._check_collector_processed_data()

    assert bot_status_check.writer.status is None
    assert (
        "OK: Collector processed data in last 2 days, 0:00:00"
        in bot_status_check.writer._summary_lines
    )


def test_check_collector_proceeds_data_skipped_on_not_collectors(
    bot_status_check, runtime
):
    runtime["test-bot"] = {"groupname": "experts", "enabled": True}

    bot_status_check._check_collector_processed_data()

    assert bot_status_check.writer.status is None
    assert not bot_status_check.writer._summary_lines


def test_check_collector_proceeds_data_not_fail_on_restarts(bot_status_check, runtime):
    """IntelMQ resets stats cache on bot restarts"""
    runtime["test-bot"] = {"groupname": "collectors", "enabled": True}
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 9},
        {
            "time": (datetime.now() - timedelta(days=1, hours=10)).isoformat(),
            "value": 0,
        },
        {"time": (datetime.now() - timedelta(days=1, hours=9)).isoformat(), "value": 4},
        {"time": (datetime.now() - timedelta(days=1, hours=8)).isoformat(), "value": 1},
        {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 9},
    ]

    bot_status_check._check_collector_processed_data()

    assert bot_status_check.writer.status is None
    assert (
        "OK: Collector processed data in last 2 days, 0:00:00"
        in bot_status_check.writer._summary_lines
    )


def test_check_collector_proceeds_data_fail(bot_status_check, runtime):
    runtime["test-bot"] = {"groupname": "collectors", "enabled": True}
    # this check just uses cache updated by separated method
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 7},
        {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
    ]

    bot_status_check._check_collector_processed_data()

    assert bot_status_check.writer.status == CheckStatus.CRITICAL
    assert (
        "FAIL: Collector processed no data in last 2 days, 0:00:00"
        in bot_status_check.writer._summary_lines
    )


def test_check_collector_proceeds_data_ignored(bot_status_check, runtime):
    runtime["test-bot"] = {
        "groupname": "collectors",
        "enabled": True,
        "parameters": {"monitoring-ignore-no-data": "Rarely becomes data"},
    }
    # this check just uses cache updated by separated method
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 7},
        {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
    ]

    bot_status_check._check_collector_processed_data()

    assert bot_status_check.writer.status is None
    assert (
        'SKIPPED: Verifying producing data skipped because: "Rarely becomes data"'
        in bot_status_check.writer._summary_lines
    )


@freeze_time("2023-03-07T14:10:00")
def test_today_stats_are_reported(bot_status_check):
    # 'Today' changes are reported as difference between first today seen value and the current
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": "2023-03-06T23:59:00", "value": 5},
        {"time": "2023-03-07T01:00:00", "value": 6},
        {"time": "2023-03-07T12:00:00", "value": 8},
    ]
    bot_status_check.storage["successes-timeline"] = [
        {"time": "2023-03-06T23:59:00", "value": 4},
        {"time": "2023-03-07T01:00:00", "value": 5},
        {"time": "2023-03-07T12:00:00", "value": 8},
    ]
    bot_status_check.storage["failures-timeline"] = [
        {"time": "2023-03-06T23:59:00", "value": 1},
        {"time": "2023-03-07T01:00:00", "value": 2},
        {"time": "2023-03-07T12:00:00", "value": 2},
    ]

    bot_status_check._report_today_stats()

    assert "today-produced=2.00;;" in bot_status_check.writer._metrics
    assert "today-succeeded=3.00;;" in bot_status_check.writer._metrics
    assert "today-failures=0.00;1;100" in bot_status_check.writer._metrics


@freeze_time("2023-03-07T14:10:00")
def test_today_stats_are_reported_after_restart(bot_status_check):
    # If bot was restarted, IntelMQ resets its total stats;
    # the cached data will have a restart point
    bot_status_check.storage["total-processed-timeline"] = [
        {"time": "2023-03-07T01:00:00", "value": 9},
        {"time": "2023-03-07T02:00:00", "value": 15},
        {"time": "2023-03-07T03:00:00", "value": 1},
        {"time": "2023-03-07T12:00:00", "value": 8},
        {"time": "2023-03-07T12:00:00", "value": 0},
    ]
    bot_status_check.storage["successes-timeline"] = [
        {"time": "2023-03-07T01:00:00", "value": 3},
        {"time": "2023-03-07T02:00:00", "value": 5},
        {"time": "2023-03-07T03:00:00", "value": 1},
        {"time": "2023-03-07T12:00:00", "value": 8},
        {"time": "2023-03-07T12:00:00", "value": 2},
    ]
    bot_status_check.storage["failures-timeline"] = [
        {"time": "2023-03-07T01:00:00", "value": 3},
        {"time": "2023-03-07T02:00:00", "value": 3},
        {"time": "2023-03-07T03:00:00", "value": 1},
        {"time": "2023-03-07T12:00:00", "value": 8},
        {"time": "2023-03-07T12:00:00", "value": 8},
    ]

    bot_status_check._report_today_stats()

    assert "today-produced=14.00;;" in bot_status_check.writer._metrics
    assert "today-succeeded=12.00;;" in bot_status_check.writer._metrics
    assert "today-failures=8.00;1;100" in bot_status_check.writer._metrics


@freeze_time("2023-03-07T14:10:00")
def test_report_error_rate(bot_status_check):
    # If bot was restarted, IntelMQ resets its stats;
    # the cached data will have a restart point
    bot_status_check.storage["successes-timeline"] = [
        {"time": "2023-03-07T01:00:00", "value": 3},
        {"time": "2023-03-07T02:00:00", "value": 5},
        {"time": "2023-03-07T03:00:00", "value": 1},
        {"time": "2023-03-07T12:00:00", "value": 8},
        {"time": "2023-03-07T12:00:00", "value": 2},
    ]
    bot_status_check.storage["failures-timeline"] = [
        {"time": "2023-03-07T01:00:00", "value": 3},
        {"time": "2023-03-07T02:00:00", "value": 3},
        {"time": "2023-03-07T03:00:00", "value": 1},
        {"time": "2023-03-07T12:00:00", "value": 8},
        {"time": "2023-03-07T12:00:00", "value": 8},
    ]

    bot_status_check._report_error_rate()

    # For more accurate results, the error rate period
    # and collector activity windows are separated
    assert (
        "Error rate for last 1 day, 23:00:00 is 40.00%"
        in bot_status_check.writer._summary_lines
    )
    assert "period-error-percentage=40.00;1;10" in bot_status_check.writer._metrics


def test_report_current_queues_size(runtime, bot_status_check, bot_queues):
    runtime["test-bot"] = {}
    bot_queues["test-bot"] = {
        "source_queue": ("test-bot-input", 560),
        "internal_queue": 465,
        "destination_queues": [("dest-1", 56), ("dest-2", 451)],
    }

    bot_status_check._report_queues_size()

    assert "input-queue=560.00;20000;50000" in bot_status_check.writer._metrics
    assert "internal-queue=465.00;20000;50000" in bot_status_check.writer._metrics

    # Size of destination queues should be verified by processing bots
    # Here reported just informational
    assert "destination-dest-1=56.00;;" in bot_status_check.writer._metrics
    assert "destination-dest-2=451.00;;" in bot_status_check.writer._metrics


def test_report_current_queues_size_custom_limits(
    bot_status_check, bot_queues, runtime
):
    bot_queues["test-bot"] = {
        "source_queue": ("test-bot-input", 560),
        "internal_queue": 465,
        "destination_queues": [("dest-1", 56), ("dest-2", 451)],
    }
    runtime["test-bot"] = {
        "parameters": {
            "monitoring-queue-warning": 70000,
            "monitoring-queue-critical": 140000,
        }
    }

    bot_status_check._report_queues_size()

    assert "input-queue=560.00;70000;140000" in bot_status_check.writer._metrics
    assert "internal-queue=465.00;70000;140000" in bot_status_check.writer._metrics


@pytest.mark.parametrize(
    "missed", ["source_queue", "internal_queue", "destination_queues"]
)
def test_reporting_queues_size_handles_missing_data(
    bot_status_check, bot_queues, missed, runtime
):
    runtime["test-bot"] = {}
    bot_queues["test-bot"] = {
        "source_queue": ("test-bot-input", 560),
        "internal_queue": 465,
        "destination_queues": [("dest-1", 56), ("dest-2", 451)],
    }

    del bot_queues["test-bot"][missed]

    bot_status_check._report_queues_size()
