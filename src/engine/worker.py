
import logging
import os
import signal
import socket
import sys


def _worker_signal_handler(signum, frame):
    sys.exit(0)

def _create_engine():
    from src.engine.core.engine import Engine
    return Engine()

def _setup_socket_app_logger():
    from logging.handlers import TimedRotatingFileHandler
    log_level = logging.INFO
    app_logger = logging.getLogger("engine-socketapp")
    app_logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')

    from src.config.settings import LOGS_DIR
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR,'engine-socketapp.log'), when='MIDNIGHT', backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)

    return app_logger

def _create_app(engine):
    from src.config.engine import EngineSocketAPI
    from src.engine.api.healthcheck import health_check
    from src.engine.api.inference import inference
    from src.libs.socket_protocol.server import SocketApplicaltion


    app_logger = _setup_socket_app_logger()

    app = SocketApplicaltion(logger=app_logger, timeout=20)

    setattr(app.state, "engine", engine)


    app.register(EngineSocketAPI.HEALTH_CHECK, health_check, "Health Check API")
    app.register(EngineSocketAPI.INFERENCE, inference, "Inference API")
    # app_logger.info('All of API:\n %s', app.api_documents())
    return app



def start_server_worker(server_socket: socket.socket, ready_event=None) -> None:
    """Start a simple server worker that listens on a Unix domain socket."""

    signal.signal(signal.Signals.SIGINT, _worker_signal_handler)
    signal.signal(signal.Signals.SIGTERM, _worker_signal_handler)
    pid = os.getpid()

    # The engine logger has been set up on master.
    logger = logging.getLogger("engine")

    logger.info("Booting worker with pid: %d", pid)
    logger.info("Waiting for application startup.")
    engine = _create_engine()
    app = _create_app(engine=engine)
    logger.info("Application startup complete.")
    logger.info("Started server process [%d]", pid)

    if ready_event is not None:
        ready_event.set() # type: ignore
    try:
        app.run(server_socket)
    except (KeyboardInterrupt, SystemExit):
        pass
    logger.info("Shutting down")
    logger.info("Waiting for application shutdown.")
    engine.cleanup()
    logger.info("Application shutdown complete.")
    logger.info("Finished server process [%d]", pid)


__all__ = [
    "start_server_worker",
]
