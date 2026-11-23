import logging
import sys

from watcher import ollama_health, poller
from watcher.config import WatcherConfigError, load_config


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger = logging.getLogger("watcher")
    try:
        config = load_config()
    except WatcherConfigError as exc:
        logger.error(str(exc))
        return 1

    ok, message = ollama_health.check(config)
    (logger.info if ok else logger.warning)(message)

    try:
        poller.run_forever(config)
    except WatcherConfigError as exc:
        logger.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
