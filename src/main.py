import os
import sys
from multiprocessing.shared_memory import SharedMemory

# Do not import the implemented module (or any objects from the implementation) as global variables.
# The following imports are performed by the main function.


def _engine_process(ready_event=None):
    from src.engine_master import engine_target
    engine_target(ready_event)


_logger = None


def _setup_logging():
    import logging

    from src.config.constants import MAIN_LOGGER_NAME
    from src.config.settings import LOGS_DIR, NUM_LOG_BACKUP
    log_level = logging.INFO
    logger = logging.getLogger(MAIN_LOGGER_NAME)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] - %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    from logging.handlers import TimedRotatingFileHandler

    file_handler = TimedRotatingFileHandler(os.path.join(
        LOGS_DIR, f"{MAIN_LOGGER_NAME}.log"), when='MIDNIGHT', backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _create_resources() -> tuple[list[SharedMemory], list[tuple[str, ...]]]:

    from src.config.constants import SHM_HEADER_SIZE
    from src.config.settings import (GUNICORN_NUM_WORKERS, RESOURCE_SHM_INPUT_SIZE_MB,
                                     RESOURCE_SHM_OUTPUT_SIZE_MB)
    _logger.info("Creating shared resources using beween processes")

    shm_list: list[SharedMemory] = []
    name_tuples: list[tuple[str, ...]] = []
    NUM_TUPLES = GUNICORN_NUM_WORKERS + 1  # Backup 1
    INPUT_SIZE = RESOURCE_SHM_INPUT_SIZE_MB * 1024 * 1024 + SHM_HEADER_SIZE
    OUTPUT_SIZE = RESOURCE_SHM_OUTPUT_SIZE_MB * 1024 * 1024 + SHM_HEADER_SIZE
    for i in range(NUM_TUPLES):
        input_shm = SharedMemory(
            name=f"Shm_I_{i + 1:02d}", create=True, size=INPUT_SIZE)
        output_shm = SharedMemory(
            name=f"Shm_O_{i + 1:02d}", create=True, size=OUTPUT_SIZE)
        shm_list.append(input_shm)
        shm_list.append(output_shm)
        name_tuples.append((input_shm.name, output_shm.name))

    _logger.info("Created shared resources: %s", shm_list)
    return shm_list, name_tuples

def _log_shared_config():
    from src.config.settings import USING_SHM_LOCK, DEATHLOCKS_CHECKING
    _logger.info("[Shared Config]: USING_SHM_LOCK = %s", USING_SHM_LOCK)
    _logger.info("[Shared Config]: DEATHLOCKS_CHECKING = %s", DEATHLOCKS_CHECKING)


def _cleanup_resources(shm_list: list[SharedMemory]):
    for shm in shm_list:
        try:
            shm.close()
            shm.unlink()
        except Exception as e:
            _logger.warning("Error while releasing shared memory: %s", e)


def _load_env():
    import argparse
    parser = argparse.ArgumentParser(
        description="Check resource and engine services is ready")

    parser.add_argument("-e", "--env_file", default=None,
                        help="Envirionment file to load. Default to None")

    args = parser.parse_args()
    env_file = args.env_file
    if env_file:
        import dotenv
        dotenv.load_dotenv(env_file)


def main():

    _load_env()

    global _logger
    _logger = _setup_logging()

    shm_list, name_tuples = _create_resources()
    _log_shared_config()
    import secrets
    key = secrets.token_hex(8)
    del secrets
    from src import shared
    shared.initialize(name_tuples, key)

    from multiprocessing import Event, Process

    _logger.info("Starting Engine and Web Application")

    _logger.info("Starting Engine Application")
    engine_ready_event = Event()
    engine_p = Process(target=_engine_process, args=(engine_ready_event,))
    engine_p.start()

    # Wait for the engine process to signal that it's ready
    # Wait interval 5 seconds for quick exit if engine failed to start.
    engine_start_success = True
    for _ in range(6):
        if not engine_ready_event.wait(timeout=5):
            if not engine_p.is_alive():
                engine_start_success = False
                break
        else:
            break

    if not engine_ready_event.is_set() and engine_p.is_alive():
        # Timeout 30 seconds
        _logger.error(
            "Engine process taking too long time for ready, going to terminate it.")
        engine_p.terminate()
        engine_p.join()
        engine_start_success = False

    if not engine_start_success:
        _logger.error("Engine process failed to start.")
        _cleanup_resources(shm_list)
        sys.exit(1)

    _logger.info("Engine process start success with PID: %d", engine_p.pid)

    _logger.info("Initialize resources manager")

    try:
        shared.init_rs_manager(key)
    except Exception as e:
        import traceback
        _logger.error("Failed to init resources manager: %s",
                      traceback.format_exc())
        engine_p.terminate()
        engine_p.join()
        _cleanup_resources(shm_list)

    # Now, the web application worker(s) can use resources manager after fork.
    # The engine master (also engine worker) cannot use because before create engine process the resouces manager is not initialized

    _logger.info("Resources manager initialize complete")

    _logger.info("Start & Running Web Application")
    from src.web_master import start_web_application_server

    try:
        start_web_application_server()
    except KeyboardInterrupt:
        _logger.info("Shutting down program")
    except Exception:
        import traceback
        _logger.error(traceback.format_exc())
    except SystemExit as e:
        if e.code != 0:
            from src.config.settings import GUNICORN_ERROR_LOG_FILE
            _logger.error(
                "Unable to start the web application. Please open '%s' to view the details.", GUNICORN_ERROR_LOG_FILE)

    _logger.info("Terminate Engine Application")
    engine_p.terminate()
    engine_p.join()

    _logger.info("Cleanup shared resources")
    _cleanup_resources(shm_list)
    shared.cleanup(key)
    _logger.info("Program terminated successfully.")


if __name__ == '__main__':
    main()
