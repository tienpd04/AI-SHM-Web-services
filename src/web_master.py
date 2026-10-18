

def _setup_argv():
    import sys

    from src.config.settings import (GUNICORN_ACCESS_LOG_FILE,
                                     GUNICORN_ERROR_LOG_FILE,
                                     GUNICORN_LOG_LEVEL, GUNICORN_NUM_WORKERS,
                                     GUNICORN_TIMEOUT,
                                     GUNICORN_WORKER_CONNECTIONS, HOST, PORT)
    sys.argv.clear()
    sys.argv.append("gunicorn")
    sys.argv.append(f"-b {HOST}:{PORT}")
    sys.argv.append(f"--workers={GUNICORN_NUM_WORKERS}")
    sys.argv.append(f"--worker-class=uvicorn_worker.UvicornWorker")
    sys.argv.append(f"--timeout={GUNICORN_TIMEOUT}")
    sys.argv.append(f"--log-level={GUNICORN_LOG_LEVEL}")
    sys.argv.append(f"--access-logfile={GUNICORN_ACCESS_LOG_FILE or "-"}")
    sys.argv.append(f"--error-logfile={GUNICORN_ERROR_LOG_FILE}")
    sys.argv.append(f"--worker-connections={GUNICORN_WORKER_CONNECTIONS}")
    sys.argv.append(f"--config=src/gunicorn.conf.py")
    sys.argv.append("src.web.fastapi_app:app")


def start_web_application_server():
    _setup_argv()
    from gunicorn.app.wsgiapp import run
    run()
