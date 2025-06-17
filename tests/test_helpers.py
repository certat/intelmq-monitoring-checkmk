from datetime import datetime

from intelmq_monitoring_checkmk.helpers import is_collector, sum_timeline


def test_is_collector_using_groupname():
    assert is_collector({"groupname": "collectors"}) is True
    assert is_collector({"groupname": "experts"}) is False


def test_is_collector_using_group():
    assert is_collector({"group": "Collector"}) is True
    assert is_collector({"group": "Expert"}) is False


def test_is_collector_when_none():
    assert is_collector({}) is False


def test_sum_timeline_on_empty_iterator():
    today_checkpoints = filter(
        lambda v: datetime.fromisoformat(v["time"]) > datetime(2022, 1, 1),
        [],
    )
    assert None is sum_timeline(today_checkpoints)
