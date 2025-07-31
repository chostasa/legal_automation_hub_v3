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
    Reuses a thread pool for performance.
    """
    try:
        partial_func = functools.partial(func, *args, **kwargs)
        future = _executor.submit(partial_func)
        return future.result()
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS_001] ❌ Error in run_in_thread: {e}\n{tb}")
        handle_error(e, code="THREAD_UTILS_001", user_message="Threaded execution failed.", raise_it=True)


def run_async(coro, *args, **kwargs):
    """
    Utility to run a coroutine when caller is not async-aware.
    - If inside an event loop, schedule the coroutine and return the task.
    - If no event loop is running, create one and block until completion.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        if loop.is_running():
            # Schedule and return the Task
            return asyncio.ensure_future(coro(*args, **kwargs))
        else:
            return loop.run_until_complete(coro(*args, **kwargs))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[THREAD_UTILS_002] ❌ Error in run_async: {e}\n{tb}")
        handle_error(e, code="THREAD_UTILS_002", user_message="Async execution failed.", raise_it=True)
