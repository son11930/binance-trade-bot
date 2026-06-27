import time
import threading
import requests
import os
from bot.logger import log_msg

class RateLimitException(Exception):
    """Custom exception raised when the bot is globally paused to avoid Binance bans."""
    def __init__(self, message, retry_after_seconds):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds

class GlobalRateLimitManager:
    """Thread-safe singleton to track API weights and enforce global rate limits."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GlobalRateLimitManager, cls).__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self.current_weight = 0
        self.pause_until = 0.0
        self.weight_lock = threading.Lock()
        self.ban_file = ".api_ban_state"
        
        # Max weight allowed per minute by Binance is 6,000.
        # We set a hard ceiling at 5,500 to gracefully pause before hitting 429.
        self.MAX_WEIGHT_LIMIT = 5500
        
        # Load persisted ban state to survive memory wipes
        self._load_ban_state()

    def _load_ban_state(self):
        if os.path.exists(self.ban_file):
            try:
                with open(self.ban_file, "r") as f:
                    saved_time = float(f.read().strip())
                    if time.time() < saved_time:
                        self.pause_until = saved_time
                        log_msg("WARNING", f"🚨 Loaded persistent API ban. Resuming in {saved_time - time.time():.1f}s")
            except Exception as e:
                log_msg("ERROR", f"Failed to read {self.ban_file}: {e}")

    def _save_ban_state(self):
        try:
            with open(self.ban_file, "w") as f:
                f.write(str(self.pause_until))
        except Exception as e:
            log_msg("ERROR", f"Failed to write {self.ban_file}: {e}")

    def check_pause(self):
        """Called before every HTTP request. Raises RateLimitException if paused."""
        wait_time = 0
        with self.weight_lock:
            now = time.time()
            if now < self.pause_until:
                wait_time = self.pause_until - now
                
            if wait_time == 0 and self.current_weight >= self.MAX_WEIGHT_LIMIT:
                # If we've organically tracked weight over the limit, pause for 10 seconds
                self.pause_until = now + 10.0
                self._save_ban_state()
                wait_time = 10.0
                
        if wait_time > 0:
            raise RateLimitException(f"Global Rate Limit active. Need to pause for {wait_time:.1f}s", wait_time)

    def update_from_headers(self, headers: dict):
        """Extracts weight from successful response headers."""
        # Binance sends X-MBX-USED-WEIGHT-1M or X-MBX-USED-WEIGHT
        weight_str = headers.get('X-MBX-USED-WEIGHT-1M') or headers.get('X-MBX-USED-WEIGHT')
        if weight_str and weight_str.isdigit():
            with self.weight_lock:
                self.current_weight = int(weight_str)

    def apply_ban(self, retry_after_seconds: int):
        """Called when receiving 429, 418, or 403."""
        with self.weight_lock:
            new_pause_time = time.time() + retry_after_seconds
            if new_pause_time > self.pause_until:
                self.pause_until = new_pause_time
                self._save_ban_state()
                log_msg("WARNING", f"🚨 GLOBAL API BAN APPLIED! Pausing all requests for {retry_after_seconds} seconds.")

# Expose a singleton instance
rate_limit_manager = GlobalRateLimitManager()

class BinanceSession(requests.Session):
    """Custom HTTP Session that intercepts traffic to enforce global rate limits."""
    
    def request(self, method, url, **kwargs):
        # 1. Pre-request Check: Halt if globally paused
        rate_limit_manager.check_pause()
        
        # 2. Execute Request
        response = super().request(method, url, **kwargs)
        
        # 3. Post-request: Update Weight from Headers
        rate_limit_manager.update_from_headers(response.headers)
        
        # 4. Handle HTTP Errors (429, 418, 403)
        if response.status_code in (429, 418):
            retry_after_str = response.headers.get('Retry-After', '60')
            try:
                retry_after = int(retry_after_str)
            except ValueError:
                retry_after = 60
                
            rate_limit_manager.apply_ban(retry_after)
            raise RateLimitException(f"HTTP {response.status_code} Hit! Banned for {retry_after}s.", retry_after)
            
        elif response.status_code == 403:
            rate_limit_manager.apply_ban(300)
            raise RateLimitException("HTTP 403 WAF Ban Hit! Banned for 5 minutes.", 300)
            
        return response
