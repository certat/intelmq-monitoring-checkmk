import json
import logging
from datetime import datetime
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


class Storage(dict):
    def __init__(self, config: Config, name: str) -> None:
        self._config = config
        self._name = name
        self._load()

    def _load(self):
        base_dir = Path(self._config.STORAGE_DIR)
        if not base_dir.exists():
            logger.info("Creating basedir")
            base_dir.mkdir(parents=True)

        storage_file = base_dir.joinpath(f"{self._name}.json")
        if not storage_file.exists():
            logger.info("Storage file doesn't exist, skipping loading")
            return

        logger.debug("Loading file %s/%s.json", self._config.STORAGE_DIR, self._name)
        with open(
            Path(self._config.STORAGE_DIR).joinpath(f"{self._name}.json"), "r+"
        ) as f:
            self.update(json.load(f))

    def save(self):
        logger.debug("Saving file %s/%s.json", self._config.STORAGE_DIR, self._name)
        with open(
            Path(self._config.STORAGE_DIR).joinpath(f"{self._name}.json"), "w+"
        ) as f:
            json.dump(self, f)

    def add_timeline_entry(self, key: str, value):
        """Append a value to the timeline-organized cache key"""
        if key not in self:
            self[key] = list()
        current_time = datetime.utcnow()
        if self.get(key):
            last_point = self[key][-1]
            if (
                last_point["value"] == value
                and datetime.fromisoformat(last_point["time"])
                > current_time - self._config.TIMELINE_RATE_LIMIT
            ):
                logger.debug("Skipping repeating value during rate limit window")
                return
        self[key].append(dict(time=datetime.utcnow().isoformat(), value=value))

    def clean_timeline_key(self, key: str, threshold: datetime):
        """Remove entries from given timeline-organized key that are older than threshold"""
        logger.debug("Cleaning timeline %s with threshold %s", key, threshold)
        if self.get(key) and datetime.fromisoformat(self[key][0]["time"]) > threshold:
            logger.debug("Skipping cleaning timeline, no old entries")
            return
        self[key] = list(
            filter(lambda v: datetime.fromisoformat(v["time"]) > threshold, self[key])
        )
