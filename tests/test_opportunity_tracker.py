import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.opportunity_tracker import track_opportunities

def create_mock_decision(did, symbol, direction, eval_time):
    d = MagicMock()
    d.id = did
    d.symbol = symbol
    d.proposed_direction = direction
    d.timestamp = eval_time
    d.ai_reasoning = "Test"
    return d

@patch("bot.opportunity_tracker.send_discord_alert")
@patch("bot.opportunity_tracker.client.get_klines")
@patch("bot.opportunity_tracker.SessionLocalFutures")
@patch("bot.opportunity_tracker.SessionLocalSpot")
def test_track_opportunities_win(mock_spot, mock_futures, mock_get_klines, mock_alert):
    """Test standard win (missed opportunity) detection."""
    # Setup DB mock
    mock_db = MagicMock()
    eval_time = datetime.now(timezone.utc)
    d = create_mock_decision(1, "BTCUSDT", "LONG", eval_time)
    
    # Only return one decision on futures, empty on spot
    mock_spot.return_value = MagicMock()
    mock_spot.return_value.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    
    mock_futures.return_value = mock_db
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [d]
    mock_db.query.return_value.get.return_value = d
    
    # Mock klines [open_time, open, high, low, close, volume...]
    # Entry price is 100
    mock_get_klines.return_value = [
        [0, 0, 0, 0, 100.0], # Eval candle
        [0, 0, 102.0, 99.0, 0] # Next candle: hit 102 (+2%)
    ]
    
    track_opportunities()
    
    assert d.retroactive_outcome == "Win"
    assert d.max_pnl_reached == 2.0
    mock_alert.assert_called_once()

@patch("bot.opportunity_tracker.client.get_klines")
@patch("bot.opportunity_tracker.SessionLocalFutures")
@patch("bot.opportunity_tracker.SessionLocalSpot")
def test_track_opportunities_short_trade(mock_spot, mock_futures, mock_get_klines):
    """Test short trade PnL inversion."""
    mock_db = MagicMock()
    eval_time = datetime.now(timezone.utc)
    d = create_mock_decision(2, "ETHUSDT", "SHORT", eval_time)
    
    mock_spot.return_value = MagicMock()
    mock_spot.return_value.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    
    mock_futures.return_value = mock_db
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [d]
    mock_db.query.return_value.get.return_value = d
    
    # Entry price 100, drops to 98. SHORT should be +2.0% PnL
    mock_get_klines.return_value = [
        [0, 0, 0, 0, 100.0],
        [0, 0, 101.0, 98.0, 0]
    ]
    
    track_opportunities()
    
    assert d.retroactive_outcome == "Win"
    assert d.max_pnl_reached == 2.0

@patch("bot.opportunity_tracker.client.get_klines")
@patch("bot.opportunity_tracker.SessionLocalFutures")
@patch("bot.opportunity_tracker.SessionLocalSpot")
def test_track_opportunities_intra_candle_volatility(mock_spot, mock_futures, mock_get_klines):
    """Test when both TP and SL are hit in the exact same candle."""
    mock_db = MagicMock()
    eval_time = datetime.now(timezone.utc)
    d = create_mock_decision(3, "BTCUSDT", "LONG", eval_time)
    
    mock_spot.return_value = MagicMock()
    mock_spot.return_value.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    
    mock_futures.return_value = mock_db
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [d]
    mock_db.query.return_value.get.return_value = d
    
    # Drops to 90 (-10%) and hits 110 (+10%). SL is checked first!
    mock_get_klines.return_value = [
        [0, 0, 0, 0, 100.0],
        [0, 0, 110.0, 90.0, 0]
    ]
    
    track_opportunities()
    
    # It should correctly classify as a Loss because min_pnl <= -1.5 is checked first for safety.
    assert d.retroactive_outcome == "Loss"
    assert d.max_loss_reached == -10.0

@patch("bot.opportunity_tracker.client.get_klines")
@patch("bot.opportunity_tracker.SessionLocalFutures")
@patch("bot.opportunity_tracker.SessionLocalSpot")
def test_track_opportunities_insufficient_klines(mock_spot, mock_futures, mock_get_klines):
    """Test boundary condition of 0 or 1 kline."""
    mock_db = MagicMock()
    eval_time = datetime.now(timezone.utc)
    d = create_mock_decision(4, "BTCUSDT", "LONG", eval_time)
    
    mock_spot.return_value = MagicMock()
    mock_spot.return_value.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    
    mock_futures.return_value = mock_db
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [d]
    mock_db.query.return_value.get.return_value = d
    
    mock_get_klines.return_value = [[0, 0, 0, 0, 100.0]] # Only 1 kline
    
    track_opportunities()
    
    # It should hit the `continue` and not evaluate.
    assert d.retroactive_outcome is not "Win"
    assert d.retroactive_outcome is not "Loss"
