import subprocess
from unittest import mock

from intelmq_monitoring_checkmk.checks.duplicated_processes import (
    DuplicatedProcessesCheck,
)
from intelmq_monitoring_checkmk.writer import CheckStatus


def test_check_pass_when_no_duplicated_processes(monkeypatch, config):
    run_mock = mock.Mock(return_value=mock.Mock(stdout=""))
    monkeypatch.setattr(subprocess, "run", run_mock)

    check = DuplicatedProcessesCheck(config)
    check.proceed()

    assert check.writer.status == CheckStatus.OK
    assert "duplicated-processes=0.00;;" in check.writer._metrics


def test_check_fails_when_duplicated_processes(monkeypatch, config):
    output = """ 2022 64880 /usr/bin/python3 /usr/local/bin/intelmq.bots.collectors.rt.collector_rt rt-ss-freak-collector
07:01 5 /usr/bin/python3 /usr/local/bin/intelmq.bots.collectors.rt.collector_rt rt-ss-freak-collector
Mar13 26777 /usr/bin/python3 /usr/local/bin/intelmq.bots.collectors.rt.collector_rt rt-sslv2-https
Mar13 8 /usr/bin/python3 /usr/local/bin/intelmq.bots.collectors.rt.collector_rt rt-sslv2-https"""  # noqa
    run_mock = mock.Mock(return_value=mock.Mock(stdout=output))
    monkeypatch.setattr(subprocess, "run", run_mock)

    check = DuplicatedProcessesCheck(config)
    check.proceed()

    assert check.writer.status == CheckStatus.CRITICAL
    assert "duplicated-processes=4.00;;" in check.writer._metrics
