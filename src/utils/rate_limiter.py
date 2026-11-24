import time
from typing import Dict

class RateLimiter:
    def __init__(self):
        self.cooldowns: Dict[str, Dict[str, float]] = {}
        self.COMMAND_COOLDOWN = 5
        self.SUGGESTION_APPLICATION_COOLDOWN = 30
    
    def check_cooldown(self, user_id: str, command: str, cooldown: int = None) -> tuple[bool, int]:
        if cooldown is None:
            cooldown = self.COMMAND_COOLDOWN
        
        now = time.time()
        user_cooldowns = self.cooldowns.setdefault(user_id, {})
        last_used = user_cooldowns.get(command, 0)
        
        if now - last_used < cooldown:
            remaining = int(cooldown - (now - last_used))
            return False, remaining
        
        user_cooldowns[command] = now
        return True, 0
    
    def clear_user(self, user_id: str) -> None:
        if user_id in self.cooldowns:
            del self.cooldowns[user_id]

rate_limiter = RateLimiter()

COMMAND_COOLDOWN = 5
SUGGESTION_APPLICATION_COOLDOWN = 30