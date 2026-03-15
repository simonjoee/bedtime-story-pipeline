import asyncio
import logging

logger = logging.getLogger(__name__)

def async_retry(max_attempts=3, base_delay=2, backoff_factor=2):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
