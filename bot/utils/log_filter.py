import time
import logging
from typing import Dict

class ThrottledLogFilter(logging.Filter):
    """
    A logging filter that suppresses identical log messages (or messages matching known patterns)
    if they occur more than once within the specified `interval` seconds (default 60.0).
    When the interval expires and a new record comes through, emits a summary message of suppressed duplicates.
    """
    def __init__(self, interval: float = 60.0):
        super().__init__()
        self.interval = interval
        self._last_logged: Dict[str, float] = {}
        self._suppressed_counts: Dict[str, int] = {}
        self._summary_logger = logging.getLogger("bot.log_filter")

    def _normalize_message(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if "Read loop has been closed" in msg:
            return "Error receiving message: Read loop has been closed"
        if "Connection reset by peer" in msg:
            return "Connection reset by peer"
        if "error while receiving message" in msg.lower() or "error receiving message" in msg.lower():
            return msg.split("\n")[0][:100]
        return msg

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_throttled_filter_checked", False):
            return getattr(record, "_throttled_filter_result", True)
        record._throttled_filter_checked = True

        if record.name == "bot.log_filter" or "[Log Filter]" in record.getMessage():
            record._throttled_filter_result = True
            return True

        now = time.time()
        msg_key = self._normalize_message(record)
        last_time = self._last_logged.get(msg_key, 0.0)

        if now - last_time < self.interval:
            self._suppressed_counts[msg_key] = self._suppressed_counts.get(msg_key, 0) + 1
            record._throttled_filter_result = False
            return False
        else:
            suppressed = self._suppressed_counts.get(msg_key, 0)
            if suppressed > 0:
                self._suppressed_counts[msg_key] = 0
                summary_msg = f"[Log Filter] Suppressed {suppressed} duplicate log entries in the last {self.interval}s for: '{msg_key}'"
                self._summary_logger.warning(summary_msg)

            self._last_logged[msg_key] = now
            record._throttled_filter_result = True
            return True
