import logging
import os
import signal
import socket
import sys

from src.config.resources import (RESOURCES_SOCKET_ADDRESS,
                                  RESOURCES_SOCKET_FAMILY,
                                  RESOURCES_SOCKET_KIND, ResourcesSocketAPI)


from src.resources.logger import logger as _logger


def _setup_app_logger():
    from logging.handlers import TimedRotatingFileHandler
    log_level = logging.INFO
    logger = logging.getLogger("resources-socketapp")
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')

    from src.config.settings import LOGS_DIR, NUM_LOG_BACKUP

    file_handler = TimedRotatingFileHandler(os.path.join(LOGS_DIR, "rs-socketapp.log"), when='MIDNIGHT', backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _create_rs_manager(resources):
    from src.config.settings import NUM_WORKERS
    from src.resources.manager import ResourcesManager
    manager = ResourcesManager(
        resources, NUM_WORKERS)
    return manager


def _create_app(manager):

    from src.libs.socket_protocol.server import SocketApplicaltion
    from src.resources.apis import health_check, take_resources

    app = SocketApplicaltion(logger=_setup_app_logger(), timeout=10)

    setattr(app.state, 'manager', manager)

    app.register(ResourcesSocketAPI.HEALTH_CHECK,
                 health_check, "Health Check API")
    app.register(ResourcesSocketAPI.TAKE_RESOURCES,
                 take_resources, "Get Worker Resources")
    return app


def _signal_handler(signum, frame):
    signame = f"{signum}"
    for sig in signal.Signals:
        if signum == sig:
            signame = sig.name
            break
    _logger.info("Handling signal: %s", signame)
    sys.exit(0)


def resources_target(resources: list[tuple[str, ...]], ready_event=None):
    '''
    Objective of the Resource Management Process

    The objective of the resource management process is to manage and distribute resources among the web application worker processes (Web Application Workers).

    This service is necessary for the following reasons:

        - If a web application worker process crashes, the resources held by that process may become unusable.
        - If shared memory resources are created at runtime by a web application worker:
            - Resource management becomes difficult because the engine worker also uses these resources.
            - If the web application worker crashes, the shared memory may not be released because it is also being used by the engine worker.
            - New resources may be created repeatedly, resulting in an excessive number of resources.
            - The operating system creates a resource-tracking process for each process that uses a shared memory object. This can result in an excessive number of resource-tracking processes.

    Therefore, creating a fixed set of shared memory resources in the main process and using this service to distribute them to web application workers provides several benefits:

        - Prevents resource leaks.
        - Makes resource management easier.
        - Improves performance.
        - Optimizes the number of resource-tracking processes created by the operating system, since only one resource-tracking process is created for the main process.
    NOTE:
        - The service operates as a single, continuously running process.
        - It does not support multiple instances running simultaneously.
        - It does not support restarting the process at runtime.

    This is because the manager object uses a global variable to store the resource state:

        - When multiple processes are used, the global variable is not shared between them.
        - When the process is restarted, the global variable containing the resource state is recreated, causing the previously stored resource state to be lost.

    This limitation is acceptable because the service's tasks (APIs) are very simple:

        - Health Check API: Logs the request and returns a success response.
        - Resource Allocation API: Each web application worker process requests resources only once during its lifecycle.
    '''

    logger = _logger
    logger.info("Starting Resouces Service")
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    pid = os.getpid()
    server_socket = socket.socket(
        RESOURCES_SOCKET_FAMILY, RESOURCES_SOCKET_KIND)
    address = RESOURCES_SOCKET_ADDRESS

    if isinstance(address, str) and os.path.exists(address):
        os.remove(address)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(address)
    server_socket.listen(128)
    logger.info("Listening at: %s", str(address))
    logger.info("Waiting for application startup.")
    manager = _create_rs_manager(resources)
    app = _create_app(manager)

    logger.info("Application startup complete.")
    logger.info("Started server process [%d]", pid)
    if ready_event is not None:
        ready_event.set()  # type: ignore
    try:
        app.run(server_socket)
    except (KeyboardInterrupt, SystemExit):
        pass

    logger.info("Shutting down")
    logger.info("Waiting for application shutdown.")
    logger.info("Application shutdown complete.")
    logger.info("Finished server process [%d]", pid)
    server_socket.close()
    if isinstance(address, str) and os.path.exists(address):
        try:
            os.remove(address)
        except Exception:
            pass
