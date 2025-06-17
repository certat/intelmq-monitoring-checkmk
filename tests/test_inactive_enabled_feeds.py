import json
from datetime import datetime, timedelta

from intelmq_monitoring_checkmk.checks.inactive_enabled_feeds import InactiveFeedCheck
from intelmq_monitoring_checkmk.helpers import normalize_name


def test_report_inactive_collectors_on_empty(
    get_check_results, runtime, config, fake_stats
):
    _prepare_runtime(runtime)
    _prepare_stats(fake_stats)

    check = InactiveFeedCheck(config)
    check.check()

    assert len(check.writer._summary_lines) == 2

    results = get_check_results(check)
    assert "Collector collector-1 has 0 processed messages in last " in results
    assert "Collector collector-2 has 0 processed messages in last " in results
    assert "inactive_feeds=2.00;" in results


def test_report_inactive_collectors_with_previous_data(
    get_check_results,
    runtime,
    config,
    fake_stats,
    storage_dir,
):
    _prepare_runtime(runtime)
    _prepare_stats(fake_stats)

    history_data = {
        "collector-1": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 3},
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 7},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
        ],
        "collector-2": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 9},
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 20},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 20},
        ],
    }

    storage_name = normalize_name(
        f"{InactiveFeedCheck.PREFIX}-{InactiveFeedCheck.NAME}.json"
    )
    with open(storage_dir / storage_name, "w+") as f:
        json.dump(history_data, f)

    check = InactiveFeedCheck(config)
    check.check()

    assert len(check.writer._summary_lines) == 2
    results = get_check_results(check)
    assert "Collector collector-1 has 0 processed messages in last " in results
    assert "Collector collector-2 has 0 processed messages in last " in results
    assert "inactive_feeds=2.00;" in results


def test_report_inactive_collectors_with_custom_periods(
    get_check_results,
    runtime,
    config,
    fake_stats,
    storage_dir,
):
    _prepare_runtime(runtime)
    _prepare_stats(fake_stats)
    runtime["collector-2"]["parameters"] = {"monitoring-activity-window-days": 14}

    history_data = {
        "collector-1": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 3},
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 7},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
        ],
        "collector-2": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 9},
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 20},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 20},
        ],
    }

    storage_name = normalize_name(
        f"{InactiveFeedCheck.PREFIX}-{InactiveFeedCheck.NAME}.json"
    )
    with open(storage_dir / storage_name, "w+") as f:
        json.dump(history_data, f)

    check = InactiveFeedCheck(config)
    check.check()

    assert len(check.writer._summary_lines) == 1
    results = get_check_results(check)
    assert "Collector collector-1 has 0 processed messages in last " in results
    assert "inactive_feeds=1.00;" in results


def test_check_passed_with_data(
    get_check_results,
    runtime,
    config,
    fake_stats,
    storage_dir,
):
    _prepare_runtime(runtime)
    _prepare_stats(fake_stats)

    history_data = {
        "collector-1": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 3},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
            {
                "time": (datetime.now() - timedelta(days=1)).isoformat(),
                "value": 2,
            },  # restart
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
        ],
        "collector-2": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 9},
            # Ensure the check sums all total paths
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 15},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 15},
        ],
    }

    storage_name = normalize_name(
        f"{InactiveFeedCheck.PREFIX}-{InactiveFeedCheck.NAME}.json"
    )
    with open(storage_dir / storage_name, "w+") as f:
        json.dump(history_data, f)

    check = InactiveFeedCheck(config)
    check.check()

    assert len(check.writer._summary_lines) == 0
    results = get_check_results(check)
    assert "inactive_feeds=0.00;" in results


def test_report_ignored_inactive_collector(
    get_check_results,
    runtime,
    config,
    fake_stats,
    storage_dir,
):
    runtime.update(
        {
            "collector-1": {
                "groupname": "collectors",
                "enabled": True,
                "parameters": {"monitoring-ignore-no-data": "Rarely becomes data"},
            },
        }
    )
    _prepare_stats(fake_stats)

    history_data = {
        "collector-1": [
            {"time": (datetime.now() - timedelta(days=3)).isoformat(), "value": 3},
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "value": 7},
            {"time": (datetime.now() - timedelta(days=1)).isoformat(), "value": 7},
        ],
    }

    storage_name = normalize_name(
        f"{InactiveFeedCheck.PREFIX}-{InactiveFeedCheck.NAME}.json"
    )
    with open(storage_dir / storage_name, "w+") as f:
        json.dump(history_data, f)

    check = InactiveFeedCheck(config)
    check.check()

    assert len(check.writer._summary_lines) == 1
    assert (
        'SKIPPED collector collector-1, reason: "Rarely becomes data"'
        in check.writer._summary_lines
    )
    results = get_check_results(check)
    assert "inactive_feeds=0.00;" in results
    assert "skipped_during_check=1.00;" in results


def _prepare_stats(fake_stats):
    fake_stats["collector-1.total._default"] = "7"
    fake_stats["collector-2.total._default"] = "15"
    fake_stats["collector-2.total._alternative"] = "5"
    fake_stats["collector-disabled.total._default"] = "0"
    fake_stats["expert.total._default"] = "0"


def _prepare_runtime(runtime):
    runtime.update(
        {
            "collector-1": {"groupname": "collectors", "enabled": True},
            "collector-2": {"groupname": "collectors", "enabled": True},
            "collector-disabled": {"groupname": "collectors", "enabled": False},
            "expert": {"groupname": "experts", "enabled": True},
        }
    )
