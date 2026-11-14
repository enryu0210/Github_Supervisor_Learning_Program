import logging
import sys

from watcher import poller
from watcher.config import WatcherConfigError, load_config


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        config = load_config()
    except WatcherConfigError as exc:
        logging.getLogger("watcher").error(str(exc))
        return 1

    poller.run_forever(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
