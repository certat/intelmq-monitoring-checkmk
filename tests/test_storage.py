import json
from datetime import datetime

from freezegun import freeze_time

from intelmq_monitoring_checkmk.storage import Storage


def test_storage_creates_new_file(storage_dir, config):
    storage = Storage(config, "my-name")
    storage["some-data-key"] = "my value"
    storage.save()

    with open(storage_dir / "my-name.json") as f:
        assert json.load(f) == {"some-data-key": "my value"}


def test_storage_reads_and_updates_data(storage_dir, config):
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump({"data-1": "val-1", "data-2": "val-2"}, f)

    storage = Storage(config, "my-name")
    assert storage["data-1"] == "val-1"
    assert storage["data-2"] == "val-2"

    storage["data-2"] = "new value"
    storage["data-3"] = "new key"
    storage.save()

    with open(storage_dir / "my-name.json") as f:
        data = json.load(f)
    assert data == {"data-1": "val-1", "data-2": "new value", "data-3": "new key"}


def test_storage_creates_and_updates_timeline(storage_dir, config):
    storage = Storage(config, "my-name")

    with freeze_time("2023-03-08T12:00"):
        storage.add_timeline_entry("timeline-key", 56)

    with freeze_time("2023-03-09T22:00"):
        storage.add_timeline_entry("timeline-key", 118)

    storage.save()

    with open(storage_dir / "my-name.json") as f:
        data = json.load(f)
    assert data == {
        "timeline-key": [
            {"time": "2023-03-08T12:00:00", "value": 56},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }


def test_storage_updating_timeline_skipped_if_recently_done_and_no_changes(
    storage_dir, config
):
    data = {
        "timeline-key": [
            {"time": "2023-03-09T21:00:00", "value": 110},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump(data, f)

    storage = Storage(config, "my-name")
    # Default rate limit: 14 minutes
    with freeze_time("2023-03-09T22:13"):
        storage.add_timeline_entry("timeline-key", 118)

    with freeze_time("2023-03-09T22:15"):
        storage.add_timeline_entry("timeline-key", 118)

    storage.save()

    with open(storage_dir / "my-name.json") as f:
        data = json.load(f)
    assert data == {
        "timeline-key": [
            {"time": "2023-03-09T21:00:00", "value": 110},
            {"time": "2023-03-09T22:00:00", "value": 118},
            {"time": "2023-03-09T22:15:00", "value": 118},
        ]
    }


def test_storage_updating_timeline_ignores_rate_limit_on_change(storage_dir, config):
    data = {
        "timeline-key": [
            {"time": "2023-03-09T21:00:00", "value": 110},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump(data, f)

    storage = Storage(config, "my-name")
    # Default rate limit: 14 minutes
    with freeze_time("2023-03-09T22:13"):
        storage.add_timeline_entry("timeline-key", 121)

    storage.save()

    with open(storage_dir / "my-name.json") as f:
        data = json.load(f)
    assert data == {
        "timeline-key": [
            {"time": "2023-03-09T21:00:00", "value": 110},
            {"time": "2023-03-09T22:00:00", "value": 118},
            {"time": "2023-03-09T22:13:00", "value": 121},
        ]
    }


def test_storage_cleans_timeline(storage_dir, config):
    data = {
        "timeline-key": [
            {"time": "2023-03-07T12:00:00", "value": 11},
            {"time": "2023-03-08T08:00:00", "value": 56},
            {"time": "2023-03-08T12:00:00", "value": 56},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump(data, f)

    storage = Storage(config, "my-name")
    storage.clean_timeline_key("timeline-key", datetime(2023, 3, 8, 10))
    storage.save()

    with open(storage_dir / "my-name.json") as f:
        data = json.load(f)
    assert data == {
        "timeline-key": [
            {"time": "2023-03-08T12:00:00", "value": 56},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }


def test_storage_cleans_timeline_skip_when_too_young(storage_dir, config):
    data = {
        "timeline-key": [
            # Incorrect situation (newer at the beginning), but ensures cleaning was skipped
            {"time": "2023-03-09T12:00:00", "value": 11},
            {"time": "2023-03-08T08:00:00", "value": 56},
            {"time": "2023-03-08T12:00:00", "value": 56},
            {"time": "2023-03-09T22:00:00", "value": 118},
        ]
    }
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump(data, f)

    storage = Storage(config, "my-name")
    storage.clean_timeline_key("timeline-key", datetime(2023, 3, 8, 10))
    storage.save()

    with open(storage_dir / "my-name.json") as f:
        loaded_data = json.load(f)
    assert data == loaded_data


def test_storage_cleans_timeline_pass_on_empty(storage_dir, config):
    data = {"timeline-key": []}
    with open(storage_dir / "my-name.json", "w+") as f:
        json.dump(data, f)

    storage = Storage(config, "my-name")
    storage.clean_timeline_key("timeline-key", datetime(2023, 3, 8, 10))
    storage.save()

    with open(storage_dir / "my-name.json") as f:
        loaded_data = json.load(f)
    assert data == loaded_data
