import time
import logging
import pytest
from bot.utils.log_filter import ThrottledLogFilter

def test_throttled_log_filter_suppression(monkeypatch):
    filter_instance = ThrottledLogFilter(interval=60.0)
    
    current_time = [1000.0]
    monkeypatch.setattr(time, "time", lambda: current_time[0])
    
    def make_record():
        return logging.LogRecord(
            name="binance.streams",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error receiving message: Read loop has been closed",
            args=(),
            exc_info=None
        )
    
    # 1st time should pass through
    assert filter_instance.filter(make_record()) is True
    
    # 2nd time right away (1001.0) should be suppressed
    current_time[0] = 1001.0
    assert filter_instance.filter(make_record()) is False
    
    # 3rd time at 1030.0 should be suppressed
    current_time[0] = 1030.0
    assert filter_instance.filter(make_record()) is False
    
    # Check internal suppression count
    msg_key = "Error receiving message: Read loop has been closed"
    assert filter_instance._suppressed_counts.get(msg_key) == 2

def test_throttled_log_filter_expiration_summary(monkeypatch, caplog):
    filter_instance = ThrottledLogFilter(interval=60.0)
    current_time = [2000.0]
    monkeypatch.setattr(time, "time", lambda: current_time[0])
    
    def make_record():
        return logging.LogRecord(
            name="binance.streams",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Connection reset by peer",
            args=(),
            exc_info=None
        )
    
    # First record passes
    assert filter_instance.filter(make_record()) is True
    
    # Suppress 3 duplicates within the interval
    current_time[0] = 2010.0
    assert filter_instance.filter(make_record()) is False
    current_time[0] = 2020.0
    assert filter_instance.filter(make_record()) is False
    current_time[0] = 2030.0
    assert filter_instance.filter(make_record()) is False
    
    # Now advance past 60s (2061.0) and send record again
    current_time[0] = 2061.0
    with caplog.at_level(logging.WARNING):
        assert filter_instance.filter(make_record()) is True
        
    assert any("Suppressed 3 duplicate log entries in the last 60.0s for: 'Connection reset by peer'" in m for m in caplog.text.splitlines())
    assert filter_instance._suppressed_counts.get("Connection reset by peer") == 0

def test_throttled_log_filter_idempotent_double_filter():
    filter_instance = ThrottledLogFilter(interval=60.0)
    record = logging.LogRecord(
        name="binance.streams",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error receiving message: Read loop has been closed",
        args=(),
        exc_info=None
    )
    # First check (e.g. at Logger level)
    res1 = filter_instance.filter(record)
    # Second check on same LogRecord instance (e.g. when propagating to Handler level)
    res2 = filter_instance.filter(record)
    
    assert res1 is True
    assert res2 is True
    assert filter_instance._suppressed_counts.get("Error receiving message: Read loop has been closed", 0) == 0
