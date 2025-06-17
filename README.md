# IntelMQ Monitoring with CheckMK

Collection of custom scripts intended to monitor our IntelMQ instances with CheckMK.

## Scenarios

| Status  | Module                   | Description                                                                 |
| ------- | ------------------------ | --------------------------------------------------------------------------- |
| works   | `run` (running-checks)   | Ensure all checks are successfully executed.                                |
| works   | `inactive_enabled_feeds` | Ensure configured feeds sends data and we can ingest them into the workflow |
| works   | `bot_status`             | Verify state, queues etc. for every bot                                     |
| works   | `duplicated_processes`   | Look for duplicated bots                                                    |
| works   | `wrapper`                | Wrapper for cronjobs to monitor their execution                             |
| planned | `orphan_queues`          | Search for orphaned queues                                                  |
| planned | `dump_check`             | Verify if there are some dumped events (`intelmqdump`)                      |

> :warning: Error ratio calculation is currently not working fully correct and should rather be treated as a suggestion.

## Monitoring philosophy

This monitoring is intended to provide regular status of each IntelMQ bot, periodic actions and a few
global checks in a way it's easy to have an overview of the system health in a CheckMK dashboard.

The main monitoring script has to run periodically, and will generate a couple of informations that
can be picked up by the CheckMK agent. It uses the [local checks](https://docs.checkmk.com/latest/en/localchecks.html)
feature and runs independently from the CheckMK agent.

For every bot, there will be a new CheckMK service generated (and thus, you may need to accept it
in the CheckMK service discovery). On every run, the monitoring script performs a couple of checks,
e.g.:

  * is the bot running?
  * collect current queue size & check if they are not overfilled
  * collect & analyse bot stats (from built-in [statistics](https://docs.intelmq.org/latest/admin/beta-features/#statistics))
    * not that this method is still a beta feature and has a few issues (e.g. clearing on reload, counting failed retries)
      which affects the ability to properly count the error rates
    * historic data are also stored locally to improve calculations
  * has a collector produced data in last X days?

Based on that, the status of each bot is determined and reported to CheckMK using the [spool directory](https://docs.checkmk.com/latest/en/spool_directory.html).

In addition, there are some checks unrelated to specific bots - e.g. looking for duplicated IntelMQ processes.

The execution of the monitoring script has to be scheduled manually (e.g. with cron).

### How to use `monitor-wrap`

The `monitor-wrap` script is a helper for any script, especially the cronjobs. It takes an arbitrary
command, and create for it a monitoring results in nagios-format, as well as capture output to
a log file.

Usage:

```
monitor-wrap [--log-dir LOG_DIR] [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}] [--valid-for VALID_FOR] --name NAME -- COMMAND

# For example, to:
# - run command `/usr/local/bin/script.sh arg1`,
# - name the service as `intelmq-periodic-my-script` (prefix hardcoded in package config),
# - mark the check valid for 5 minutes (after this time of no changes, CheckMK mark the status as undefined)
# - use default log level and dir:
monitor-wrap --valid-for 300 --name my-script -- /usr/local/bin/script.sh arg1
```

You may want to use it for periodic actions, like e.g. database updates for some bots.

## How to deploy

1. Install the package `intelmq-monitoring-checkmk` from the PyPI in the same place (system, venv)
   where your IntelMQ is running.
2. Eventually adjust configuration (see `config.py` for available configuration, it can be overwritten
   in a file `/etc/intelmq/monitoring.json`).
3. Schedule a cronjob under the same user as the IntelMQ is using (also `intelmq`).
6. (if introducing new checks) Activate monitoring of new services in CheckMK

Also e.g.:

```bash
sudo pip3 install intelmq-monitoring-checkmk

sudo crontab -e -u intelmq
# Use the following cron rule to run every 5 minutes:
# */5 * * * * /usr/local/bin/intelmq-monitor
```

## Documentation

TODO

## Tests and linting

Development tools (test runner, linters) can be installed using `dev` extras:

```bash
   pip install -e .[dev]
```

All tests and linting tools (black, flake8, isort) can be run using tox:

```bash
tox  # run tests against a few python versions and linting
tox -epy10  # run only tests against Python 3.10
toy -elint  # run only linting
```

## Debugging and logging

You can use `--log-file` and `--log-level` arguments to collect logs and save them. If file isn't
set, logs will be printed on the standard output. Default log level is `INFO`.

## CheckMK docs

* https://docs.checkmk.com/latest/en/spool_directory.html
* https://docs.checkmk.com/latest/en/localchecks.html