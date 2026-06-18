import queue
import threading
import time
from .logger import log_msg

class AITask:
    def __init__(self, priority, symbol, task_func, args, kwargs):
        self.priority = priority # lower number = higher priority
        self.symbol = symbol
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.timestamp = time.time()
        
    def __lt__(self, other):
        # Tie breaker: timestamp (first in, first out for same priority)
        if self.priority == other.priority:
            return self.timestamp < other.timestamp
        return self.priority < other.priority

class AIQueueManager:
    def __init__(self):
        self.q = queue.PriorityQueue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name="AI_Worker_Thread")
        self.worker_thread.start()
        
    def _worker(self):
        while True:
            task = self.q.get()
            try:
                task.task_func(*task.args, **task.kwargs)
            except Exception as e:
                log_msg("ERROR", f"❌ Error in AI Queue task for {task.symbol}: {e}")
            finally:
                self.q.task_done()
                
    def submit(self, score, symbol, task_func, *args, **kwargs):
        if self.q.qsize() >= 2 and score < 2.0:
            log_msg("WARNING", f"⚠️ Load shedding {symbol} at submission (vol_surge {score:.2f}x < 2.0x) due to backlog.")
            if args and hasattr(args[0], 'update_state'):
                args[0].update_state(symbol, active_strategy="NONE")
            return

        # We use negative score so that higher score is lower priority number (processed first)
        task = AITask(-score, symbol, task_func, args, kwargs)
        self.q.put(task)
        log_msg("INFO", f"📥 Queued {symbol} for AI Evaluation (Score: {score:.2f}, Backlog: {self.q.qsize()})")

# Singleton instance
ai_queue_manager = AIQueueManager()
