#!/usr/bin/env python3
"""Monitor a persistent delivery queue.

This script polls the SQLite database used by
:class:`aicostmanager.delivery.PersistentDelivery` and displays
queue statistics along with recent failures. It is intended for
manual monitoring in a separate terminal during development.
"""

import argparse
import time
from aicostmanager.delivery import PersistentQueueManager

# ANSI color codes for basic highlighting
COLORS = {
    "queued": "\033[36m",      # cyan
    "processing": "\033[33m",  # yellow
    "done": "\033[32m",        # green
    "failed": "\033[31m",      # red
}
RESET = "\033[0m"


def render(stats, failed):
    lines = []
    lines.append(time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("Queue stats:")
    for status, count in sorted(stats.items()):
        color = COLORS.get(status, "")
        lines.append(f"  {color}{status:<10}{count}{RESET}")
    if failed:
        lines.append("")
        lines.append("Failed items:")
        for item in failed:
            lines.append(
                f"  {COLORS['failed']}id={item['id']} retry={item['retry_count']}{RESET}"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor the persistent delivery queue.")
    parser.add_argument("db_path", help="Path to SQLite queue database.")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds.",
    )
    args = parser.parse_args()

    mgr = PersistentQueueManager(args.db_path)
    try:
        while True:
            stats = mgr.stats()
            failed = mgr.list_failed(limit=10)
            print("\033[2J\033[H", end="")  # clear screen
            print(render(stats, failed))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
