from contextlib import suppress

import pytest

from intelmq_monitoring_checkmk.writer import CheckMKWriter, CheckStatus


def test_writer_uses_correct_filename(spool_dir, config):
    config.DEFAULT_TIMEOUT = 3.1  # has to be converted to int
    writer = CheckMKWriter(config, "this-is-My service")
    writer.save()
    assert (spool_dir / "3_this-is-my_service.txt").is_file()


def test_writer_saves_data_in_checkmk_format(spool_dir, config):
    writer = CheckMKWriter(config, "My service", "description\nwith enter")
    writer.add_metric("metric", 2, 1, 5)
    writer.add_summary_line("The line")
    writer.set_short_summary("First line")
    writer.save()

    with open(spool_dir / writer._file_name) as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert lines[0] == "<<<local>>>\n"
    assert lines[1] == (
        f'P "My service" metric=2.00;1;5 First line\\nThe line\\n\\n##########\\n'
        f"description\\nwith enter\\n##########\\n{config.FOOTNOTE}\\n\n"
    )


def test_writer_handles_multiple_metrics(spool_dir, config):
    writer = CheckMKWriter(config, "My service")
    writer.add_metric("metric", 2, 1, 5)
    writer.add_metric("metric2", 1)
    writer.add_metric("metric3", 7, critical_level=5)
    writer.set_short_summary("Summary")
    writer.save()

    with open(spool_dir / writer._file_name) as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert lines[1].startswith(
        'P "My service" metric=2.00;1;5|metric2=1.00;;|metric3=7.00;;5 Summary\\n'
    )


def test_counter_metrics(spool_dir, config):
    writer = CheckMKWriter(config, "My service")

    writer.increment_counter("test1")
    writer.increment_counter("test1")

    writer.increment_counter("test2", 2, 6)
    writer.increment_counter("test2")

    writer.save()
    with open(spool_dir / writer._file_name) as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert lines[1].startswith('P "My service" test1=2.00;;|test2=2.00;2;6')


def test_writer_respects_status_hierarchy(config):
    writer = CheckMKWriter(config, "My service")
    assert writer.status_char == "0"

    writer.add_metric("something", 4, 1, 3)
    assert writer.status_char == "P"

    writer.status = CheckStatus.OK
    assert writer.status_char == "0"

    writer.status = CheckStatus.WARNING
    assert writer.status_char == "1"
    writer.status = CheckStatus.OK
    assert writer.status_char == "1"

    writer.status = CheckStatus.UNKNOWN
    assert writer.status_char == "3"
    writer.status = CheckStatus.OK
    assert writer.status_char == "3"

    writer.status = CheckStatus.CRITICAL
    assert writer.status_char == "2"
    writer.status = CheckStatus.UNKNOWN
    assert writer.status_char == "2"
    writer.status = CheckStatus.OK
    assert writer.status_char == "2"


def test_writer_as_context_manager(spool_dir, config):
    with CheckMKWriter(config, "My service", timeout=3) as checkmk:
        checkmk.add_metric("metric", 2, 1, 5)

    with open(spool_dir / "3_my_service.txt") as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert lines[1].startswith("P")
    assert "metric=2.00;1;5" in lines[1]
    assert "execution-time-ms=" in lines[1]


def test_writer_as_context_manager_on_exception(spool_dir, config):
    with suppress(ValueError):
        with CheckMKWriter(config, "My service", timeout=3) as checkmk:
            checkmk.add_metric("metric", 2, 1, 5)
            raise ValueError("an error")

    with open(spool_dir / "3_my_service.txt") as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert lines[1].startswith("2")
    assert "an error" in lines[1]


def test_piggyback_hostname_validation(config):
    with pytest.raises(ValueError):
        CheckMKWriter(config, "My service", piggyback_host="../../")

    with pytest.raises(ValueError):
        CheckMKWriter(config, "My service", piggyback_host="%%2F")

    CheckMKWriter(config, "My service", piggyback_host="correct.host")


def test_piggyback_saves_correctly(spool_dir, config):
    writer = CheckMKWriter(config, "My service", timeout=3, piggyback_host="some.host")
    writer.save()

    with open(spool_dir / "3_my_service_some.host.txt") as f:
        lines = f.readlines()

    assert len(lines) == 4
    assert lines[0] == "<<<<some.host>>>>\n"
    assert lines[1] == "<<<local>>>\n"
    assert lines[2].startswith('0 "My service"')
    assert lines[3] == "<<<<>>>>\n"
