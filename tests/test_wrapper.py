from intelmq_monitoring_checkmk.checks.script_wrapper import ScriptExecutionWrapperCheck
from intelmq_monitoring_checkmk.wrapper import run
from intelmq_monitoring_checkmk.writer import CheckStatus


def test_report_fail_when_execution_failed(config):
    check = ScriptExecutionWrapperCheck(config, "test", "exit 1", valid_for=900)
    check.proceed()

    assert check.writer.status == CheckStatus.CRITICAL
    assert "execution-time-ms" in check.writer._metrics[0]


def test_report_success_on_shell_command(config):
    check = ScriptExecutionWrapperCheck(
        config, "test", "echo 'eeeee' | cat", valid_for=900
    )
    check.proceed()

    assert check.writer.status == CheckStatus.OK
    assert "execution-time-ms" in check.writer._metrics[0]


def test_respect_name_and_timeout(config):
    check = ScriptExecutionWrapperCheck(
        config, "testing", "echo 'eeeee'", valid_for=100
    )
    check.proceed()

    assert check.name == "intelmq-periodic-testing"
    assert check.writer.timeout == 100


def test_running_cli(config, spool_dir):
    assert run(config, "test", "echo aaa", 100) == 0

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        assert f.readlines()[1].startswith("0")


def test_running_cli_on_fail(config, spool_dir):
    assert run(config, "test", "exit 1", 100) == 1

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        assert f.readlines()[1].startswith("2")


def test_retry_with_fail(config, spool_dir):
    test_path = spool_dir / "retry_fail.txt"
    assert run(config, "test", f"echo -n 1 >> {test_path} && exit 1", 100, 3) == 1

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        data = f.readlines()[1]
        assert data.startswith("2")
        assert "retries=2.00" in data

    with open(test_path) as f:
        assert f.read().strip() == "111"


def test_retry_success(config, spool_dir):
    test_path = spool_dir / "retry_ok.txt"
    assert (
        run(
            config,
            "test",
            f"echo -n 1 >> {test_path} && grep -q '11' {test_path}",
            100,
            3,
        )
        == 0
    )

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        data = f.readlines()[1]
        assert data.startswith("0")
        assert "retries=1.00" in data


def test_get_json_metrics(config, spool_dir):
    assert (
        run(
            config,
            "test",
            """echo '{"important_val": 1, "other_val": 34}' """,
            100,
            json_metrics=True,
        )
        == 0
    )

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        data = f.readlines()[1]
        assert data.startswith("0")
        assert "important_val=1.00" in data
        assert "other_val=34.00" in data


def test_get_json_metrics_on_incorrect_data(config, spool_dir):
    assert (
        run(config, "test", """echo 'this is not json.' """, 100, json_metrics=True)
        == 1
    )

    with open(spool_dir / "100_intelmq-periodic-test.txt") as f:
        data = f.readlines()[1]
        assert data.startswith("1")
        assert "retries=0.00" in data  # Command succeeded, just metrics issues
        assert "Expected metrics data not found in the output" in data
