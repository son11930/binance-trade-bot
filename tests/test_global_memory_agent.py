import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.global_memory_agent import fetch_daily_stats

@patch("bot.global_memory_agent.SessionLocalFutures")
@patch("bot.global_memory_agent.SessionLocalSpot")
def test_fetch_daily_stats_empty(mock_spot, mock_futures):
    """Test when database is empty or has no recent trades/decisions."""
    mock_db = MagicMock()
    # Setup mock to return empty counts/lists
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    
    mock_spot.return_value = mock_db
    mock_futures.return_value = mock_db
    
    stats = fetch_daily_stats('spot')
    assert stats is None  # Should return None if everything is zero

@patch("bot.global_memory_agent.SessionLocalFutures")
@patch("bot.global_memory_agent.SessionLocalSpot")
def test_fetch_daily_stats_with_data(mock_spot, mock_futures):
    """Test when trades and missed opportunities exist."""
    mock_db = MagicMock()
    win1 = MagicMock(pnl_percent=5.0, timestamp=datetime.now(timezone.utc), symbol="BTCUSDT", side="BUY", ai_reasoning="test")
    win2 = MagicMock(pnl_percent=3.0, timestamp=datetime.now(timezone.utc), symbol="ETHUSDT", side="BUY", ai_reasoning="test")
    loss1 = MagicMock(pnl_percent=-2.0, timestamp=datetime.now(timezone.utc), symbol="SOLUSDT", side="BUY", ai_reasoning="test")
    
    mock_db.query.return_value.filter.return_value.all.side_effect = [
        [win1, win2], # all_wins
        [loss1]       # all_losses
    ]
    mock_db.query.return_value.filter.return_value.count.side_effect = [
        0, # Missed count (Spot)
        0, # Good blocks count (Spot)
    ]
    
    # We will just let .all() return empty lists for simplicity of this unit test
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    
    mock_spot.return_value = mock_db
    mock_futures.return_value = mock_db
    
    stats_spot = fetch_daily_stats('spot')
    
    assert stats_spot is not None
    assert stats_spot["wins"] == 2
    assert stats_spot["losses"] == 1
    assert stats_spot["missed_opportunities"] == 0
    assert stats_spot["good_blocks"] == 0

@patch("bot.global_memory_agent.SessionLocalFutures")
@patch("bot.global_memory_agent.SessionLocalSpot")
def test_fetch_daily_stats_exception_handling(mock_spot, mock_futures):
    """Test graceful handling of DB exceptions."""
    mock_spot.side_effect = Exception("DB Connection Error")
    mock_futures.side_effect = Exception("DB Connection Error")
    
    # Should not raise, should catch and return None
    stats = fetch_daily_stats('futures')
    assert stats is None
