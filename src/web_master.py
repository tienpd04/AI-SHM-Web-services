

def _setup_argv():
    import sys

    from src.config.settings import (ACCESS_LOG_FILE, ERROR_LOG_FILE, HOST,
                                     LOG_LEVEL, NUM_WORKERS, PORT,
                                     WORKER_CONNECTIONS)
    sys.argv.clear()
    sys.argv.append("gunicorn")
    sys.argv.append(f"-b {HOST}:{PORT}")
    sys.argv.append(f"--workers={NUM_WORKERS}")
    sys.argv.append(f"--worker-class=uvicorn_worker.UvicornWorker")
    sys.argv.append(f"--timeout=300")
    sys.argv.append(f"--log-level={LOG_LEVEL}")
    sys.argv.append(f"--access-logfile={ACCESS_LOG_FILE or "-"}")
    sys.argv.append(f"--error-logfile={ERROR_LOG_FILE}")
    sys.argv.append(f"--worker-connections={WORKER_CONNECTIONS}")
    sys.argv.append("src.web.fastapi_app:app")


def web_target():
    _setup_argv()
    from gunicorn.app.wsgiapp import run
    run()



def dummy_crash_web_workers():
    """For only test resources manager when web applicaion worker crash
    """

    import os
    if not os.getenv("DUMMY_CRASH_WEB_WORKERS", "").lower() == 'yes':
        raise NotImplementedError

    import time
    from multiprocessing import Event, Process

    from src.config.settings import NUM_WORKERS

    def _worker(close_event):
        from src.web.services.resources import _take_resources

        _take_resources()
        close_event.wait()

    # close_event = Event()
    wokers: list[Process] = []
    events: list[Event] = []
    for w in range(NUM_WORKERS):
        close_event = Event()
        worker = Process(target=_worker, args=(close_event,))
        worker.start()
        wokers.append(worker)
        events.append(close_event)

    time.sleep(2)
    for i in range(10):



        # Press a char and see the log in the terminal.
        print("Press 'q' (quit), 't' (terminate) or 'e' (exit) a worker and replace by new worker:", end='')
        char = input().lower().strip()

        # terminate one worker and create new for replace.
        if char == 't':
            last_wk = wokers.pop()
            last_event = events.pop()
            last_wk.terminate()
            last_wk.join()
            close_event = Event()
            new_wk = Process(target=_worker, args=(close_event,))
            new_wk.start()
            wokers.insert(0, new_wk)
            events.insert(0, close_event)

        # normal exit
        elif char == 'e':
            last_wk = wokers.pop()
            last_event = events.pop()
            last_event.set()
            last_wk.join()

            close_event = Event()
            new_wk = Process(target=_worker, args=(close_event,))
            new_wk.start()
            wokers.insert(0, new_wk)
            events.insert(0, close_event)

        elif char == 'q':
            break
        else:
            continue
        time.sleep(1)

    for evt in events:
        evt.set()
    for wk in wokers:
        wk.join()
