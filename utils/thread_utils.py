import asyncio
import concurrent.futures
import functools
import traceback
from logger import logger
from core.error_handling import handle_error


# Thread pool executor can be reused to avoid creating threads for each call
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


def run_in_thread(func, *args, **kwargs):
    """
    Run a blocking function in a separate thread and return the result.
    Maintains original behavior but reuses a thread pool for performance.
    Logs and re-raises errors with handle_error.
    """
    try:
        # Use functools.partial for cleaner submission
        partial_func = functools.partial(func, *args, **kwargs)
        future = _executor.submit(partial_func)
        return future.result()
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS] Error in run_in_thread: {e}\n{tb}")
        handle_error(e, code="THREAD_UTILS_001", user_message="Threaded execution failed.", raise_it=True)


def run_async(func, *args, **kwargs):
    """
    Run a coroutine or async function safely.
    If already inside an event loop, schedule with ensure_future.
    If not, create a new event loop and block until completion.
    Maintains original behavior but adds error handling and logging.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there's no running event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        if loop.is_running():
            # If we're inside an async context, schedule the coroutine
            return asyncio.ensure_future(func(*args, **kwargs))
        else:
            # If no event loop is running, run synchronously
            return loop.run_until_complete(func(*args, **kwargs))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS] Error in run_async: {e}\n{tb}")
        handle_error(e, code="THREAD_UTILS_002", user_message="Async execution failed.", raise_it=True)
