import re
from datetime import timedelta
from unittest import mock

import pytest
from intelmq.bin.intelmqctl import IntelMQController

from intelmq_monitoring_checkmk.base import BaseServiceCheck
from intelmq_monitoring_checkmk.config import Config


@pytest.fixture(autouse=True)
def spool_dir(tmp_path, config):
    config.CHECK_MK_SPOOL_DIR = str(tmp_path)
    yield tmp_path


@pytest.fixture(autouse=True)
def storage_dir(tmp_path, config):
    config.STORAGE_DIR = str(tmp_path)
    yield tmp_path


@pytest.fixture(autouse=True)
def config():
    cfg = Config()
    cfg.TIME_WINDOW = timedelta(days=2)
    cfg.ERROR_RATE_WINDOW = timedelta(days=1, hours=23)
    cfg.ERROR_RATE_CRITICAL = 10
    cfg.ERROR_RATE_WARNING = 1
    cfg.FAILURES_WARNING = 1
    cfg.RETRY_SLEEP = 0
    return cfg


@pytest.fixture
def cli_mock() -> IntelMQController:
    intelmq_cli = mock.Mock(auto_spec=IntelMQController)
    BaseServiceCheck._intelmq_cli = intelmq_cli
    yield intelmq_cli
    del BaseServiceCheck._intelmq_cli


class FakeRedis:
    """A very simple class to make basic unittests on bots getting data from Redis"""

    def __init__(self) -> None:
        self._data = {}

    def keys(self, template):
        # This is not exactly how redis matching works, but should be enough for our cases
        matcher = re.compile(template)
        return list(filter(lambda key: matcher.match(key), self._data.keys()))

    def get(self, key):
        return self._data.get(key, None)


@pytest.fixture
def fake_stats() -> dict:
    redis = FakeRedis()
    BaseServiceCheck._stat_db = redis
    yield redis._data
    del BaseServiceCheck._stat_db


@pytest.fixture
def get_check_results(spool_dir):
    def _get_check_results(check: BaseServiceCheck):
        with open(spool_dir / check.writer._file_name) as f:
            return f.readlines()[1]

    return _get_check_results


@pytest.fixture
def runtime():
    BaseServiceCheck._intelmq_runtime = {}
    yield BaseServiceCheck._intelmq_runtime
    del BaseServiceCheck._intelmq_runtime


@pytest.fixture
def bot_queues():
    BaseServiceCheck._bots_queues = {}
    yield BaseServiceCheck._bots_queues
    del BaseServiceCheck._bots_queues
