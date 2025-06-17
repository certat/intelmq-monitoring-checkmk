import json
from datetime import timedelta

import pytest

from intelmq_monitoring_checkmk.config import Config


def _prepare_config_file(path: str, new_config: dict):
    print(new_config)
    with open(path, "w+") as f:
        json.dump(new_config, f)


def test_loading_config_from_file(tmp_path):
    path = f"{tmp_path}/config.yaml"
    _prepare_config_file(
        path,
        {
            "footnote": "Test footnote",
            "TIME_WINDOW": {"days": 3, "minutes": 1},
            "FAILURES_WARNING": 7,
        },
    )

    config = Config(path)

    assert config.DEFAULT_TIMEOUT == Config.DEFAULT_TIMEOUT
    assert config.FOOTNOTE == "Test footnote"
    assert config.TIME_WINDOW == timedelta(days=3, minutes=1)
    assert config.FAILURES_WARNING == 7


def test_loading_config_pass_when_file_not_exists():
    config = Config("/does/not/exists.yaml")

    assert config.DEFAULT_TIMEOUT == Config.DEFAULT_TIMEOUT


@pytest.mark.parametrize(
    "cfg_data",
    [
        {"footnote": 1234},
        {"TIME_WINDOW": "wrong type"},
        {"TIME_WINDOW": {"wrong": "data"}},
        {"FAILURES_WARNING": "wrong type"},
        {"Wrong": "key"},
        {"_not": "allowed"},
    ],
)
def test_wrong_config_file_data_raises_error(tmp_path, cfg_data):
    path = f"{tmp_path}/config.yaml"
    _prepare_config_file(path, cfg_data)

    with pytest.raises((ValueError, AttributeError)):
        Config(path)
