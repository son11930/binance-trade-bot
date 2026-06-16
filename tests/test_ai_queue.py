import pytest
import time
import threading
from unittest.mock import MagicMock
from bot.ai_queue import AIQueueManager, AITask

def test_ai_task_sorting():
    # Test that AITask sorts correctly based on priority and timestamp
    # Priority is inverted score, so lower value is higher priority
    
    t1 = AITask(priority=-1.0, symbol="LOW", task_func=lambda: None, args=(), kwargs={})
    time.sleep(0.01) # Ensure different timestamps
    t2 = AITask(priority=-3.0, symbol="HIGH", task_func=lambda: None, args=(), kwargs={})
    time.sleep(0.01)
    t3 = AITask(priority=-2.0, symbol="MID", task_func=lambda: None, args=(), kwargs={})
    time.sleep(0.01)
    t4 = AITask(priority=-2.0, symbol="MID2", task_func=lambda: None, args=(), kwargs={})
    
    tasks = [t1, t2, t3, t4]
    tasks.sort()
    
    # Expected order: HIGH (-3.0), MID (-2.0), MID2 (-2.0, later timestamp), LOW (-1.0)
    assert tasks[0].symbol == "HIGH"
    assert tasks[1].symbol == "MID"
    assert tasks[2].symbol == "MID2"
    assert tasks[3].symbol == "LOW"

def test_queue_sorting_and_execution():
    qm = AIQueueManager()
    
    # We use a mock to track execution order
    execution_order = []
    
    def mock_task(name):
        execution_order.append(name)
        
    # Block the worker to queue up tasks
    block_event = threading.Event()
    
    def blocking_task():
        block_event.wait()
        
    # Submit blocking task first
    qm.submit(100.0, "BLOCKING", blocking_task)
    time.sleep(0.1) # Give worker time to pick it up
    
    # Now queue up normal tasks (scores inverted for priority)
    qm.submit(1.5, "LOW", mock_task, "LOW")
    qm.submit(3.5, "HIGH", mock_task, "HIGH")
    qm.submit(2.5, "MID", mock_task, "MID")
    
    # Unblock worker
    block_event.set()
    
    # Wait for queue to process
    qm.q.join()
    
    # The order of execution should be HIGH, MID, LOW
    # Wait, load shedding might drop LOW if qsize >= 2
    # At HIGH, qsize=2. vol_surge=3.5 >= 2.0 -> executed
    # At MID, qsize=1. vol_surge=2.5 >= 2.0 -> executed
    # At LOW, qsize=0. vol_surge=1.5 < 2.0 but qsize < 2 -> executed!
    assert execution_order == ["HIGH", "MID", "LOW"]

def test_dynamic_load_shedding():
    qm = AIQueueManager()
    
    execution_order = []
    
    def mock_task(name):
        execution_order.append(name)
        
    block_event = threading.Event()
    
    def blocking_task():
        block_event.wait()
        
    # Submit blocking task
    qm.submit(100.0, "BLOCKING", blocking_task)
    time.sleep(0.1) # Wait for worker to block
    
    # To trigger load shedding, we need qsize >= 2 when a low priority task is processed.
    # If we submit:
    # 1 task > 2.0 (HIGH)
    # 3 tasks < 2.0 (LOW1, LOW2, LOW3)
    # Order in queue: HIGH, LOW1, LOW2, LOW3
    # When LOW1 is processed: qsize=2. Score < 2.0 -> SHED
    # When LOW2 is processed: qsize=1. Score < 2.0 -> EXECUTED (qsize < 2)
    # When LOW3 is processed: qsize=0. Score < 2.0 -> EXECUTED (qsize < 2)
    
    mock_state_manager = MagicMock()
    
    qm.submit(3.0, "HIGH", mock_task, "HIGH")
    
    # We'll pass mock_state_manager as the first argument to verify unlock logic
    qm.submit(1.2, "LOW1", mock_task, mock_state_manager, "LOW1")
    qm.submit(1.1, "LOW2", mock_task, "LOW2")
    qm.submit(1.0, "LOW3", mock_task, "LOW3")
    
    block_event.set()
    qm.q.join()
    
    # LOW1 should be dropped because when it's popped, qsize=2.
    # Let's verify mock_state_manager.update_state was called
    mock_state_manager.update_state.assert_called_once_with("LOW1")
    
    # LOW1 is dropped, so it's not in execution_order. 
    # Notice mock_task for LOW1 expects two arguments (mock_state_manager, "LOW1"), 
    # but the shed logic just calls update_state and drops it.
    
    assert "HIGH" in execution_order
    assert "LOW1" not in execution_order
    assert "LOW2" in execution_order
    assert "LOW3" in execution_order

from unittest.mock import patch

def test_exception_handling_in_worker():
    qm = AIQueueManager()
    
    block_event = threading.Event()
    def blocking_task():
        block_event.wait()
        
    def error_task():
        raise ValueError("Test Exception")
        
    qm.submit(100.0, "BLOCKING", blocking_task)
    time.sleep(0.1)
    
    with patch('bot.ai_queue.log_msg') as mock_log:
        qm.submit(2.0, "ERROR_TASK", error_task)
        
        block_event.set()
        qm.q.join()
        
        # The queue should not crash and should process the task, catching the exception
        # Check if log_msg was called with ERROR and the exception message
        error_logs = [call_args for call_args in mock_log.call_args_list if call_args[0][0] == "ERROR"]
        assert len(error_logs) == 1
        assert "Test Exception" in error_logs[0][0][1]
