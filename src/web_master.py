

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
