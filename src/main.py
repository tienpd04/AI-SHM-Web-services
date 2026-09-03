import os
import sys
from multiprocessing.shared_memory import SharedMemory

# Do not import the implemented module (or any objects from the implementation) as global variables.
# The following imports are performed by the main function.


def _web_process():
    from src.web_master import web_target
    web_target()
    # from src.web_master import dummy_crash_web_workers
    # dummy_crash_web_workers()


def _engine_process(ready_event=None):
    from src.engine_master import engine_target
    engine_target(ready_event=ready_event)


def _resources_process(resources: list[tuple[str, str]], ready_event=None):
    from src.resources_master import resources_target
    resources_target(resources=resources, ready_event=ready_event)


_logger = None


def _setup_logging():
    import logging
    log_level = logging.INFO
    logger = logging.getLogger("main")
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] - %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    from logging.handlers import TimedRotatingFileHandler

    from src.config.settings import LOGS_DIR

    file_handler = TimedRotatingFileHandler(os.path.join(
        LOGS_DIR, "main.log"), when='MIDNIGHT', backupCount=7)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _create_resources() -> tuple[list[SharedMemory], list[tuple[str, str]]]:

    from src.config.settings import (NUM_WORKERS, RESOURCE_SHM_INPUT_SIZE_MB,
                                     RESOURCE_SHM_OUTPUT_SIZE_MB)
    _logger.info("Creating shared resources using beween processes")

    shm_list: list[SharedMemory] = []
    io_names: list[tuple[str, str]] = []
    NUM_IO_PAIR = NUM_WORKERS + 1  # Backup 1 (input, ouput)
    for i in range(NUM_IO_PAIR):
        input_shm = SharedMemory(
            name=f"Shm_I_{i + 1:02d}", create=True, size=RESOURCE_SHM_INPUT_SIZE_MB * 1024 * 1024)
        output_shm = SharedMemory(
            name=f"Shm_O_{i + 1:02d}", create=True, size=RESOURCE_SHM_OUTPUT_SIZE_MB * 1024 * 1024)
        shm_list.append(input_shm)
        shm_list.append(output_shm)
        io_names.append((input_shm.name, output_shm.name))

    _logger.info("Created shared resources: %s", shm_list)
    return shm_list, io_names


def _cleanup_resources(shm_list: list[SharedMemory]):
    for shm in shm_list:
        try:
            shm.close()
            shm.unlink()
        except Exception as e:
            _logger.warning(f"Error while releasing shared memory: {e}")


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


def _set_rs_api_key():
    import secrets
    os.environ["RESOURCES_API_KEY"] = secrets.token_hex(16)


def main():

    _load_env()

    _set_rs_api_key()

    global _logger
    _logger = _setup_logging()

    shm_list, io_names = _create_resources()

    from multiprocessing import Event, Process

    _logger.info("Starting Resources, Engine and Web Application")

    _logger.info("Starting Resources Application")

    rs_ready_event = Event()
    resources_p = Process(target=_resources_process,
                          args=(io_names, rs_ready_event))
    resources_p.start()

    rs_start_success = True

    # Wait for the resources process to signal that it's ready
    # Wait interval 5 seconds for quick exit if resources failed to start.
    for _ in range(6):
        if not rs_ready_event.wait(timeout=5):
            if not resources_p.is_alive():
                rs_start_success = False
                break
        else:
            break

    if not rs_ready_event.is_set() and resources_p.is_alive():
        # Timeout 30 seconds
        _logger.error(
            "Resources process taking too long time for ready, going to terminate it.")
        resources_p.terminate()
        resources_p.join()
        rs_start_success = False

    if not rs_start_success:
        _logger.error("Resources process failed to start.")
        _cleanup_resources(shm_list)
        sys.exit(1)

    _logger.info("Resources process start success with PID: %d",
                 resources_p.pid)

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
        resources_p.terminate()
        resources_p.join()
        _cleanup_resources(shm_list)
        sys.exit(1)

    _logger.info("Engine process start success with PID: %d", engine_p.pid)

    _logger.info("Start & Running Web Application")

    try:
        _web_process()
    except KeyboardInterrupt:
        _logger.info("Shutting down program")
    except Exception:
        import traceback
        _logger.error(traceback.format_exc())
    except SystemExit as e:
        if e.code != 0:
            from src.config.settings import ERROR_LOG_FILE
            _logger.error(
                "Unable to start the web application. Please open '%s' to view the details.", ERROR_LOG_FILE)

    _logger.info("Terminate Engine Application")
    engine_p.terminate()
    engine_p.join()

    _logger.info("Terminate Resources Application")
    resources_p.terminate()
    resources_p.join()

    _logger.info("Cleanup shared resources")
    _cleanup_resources(shm_list)
    _logger.info("Program terminated successfully.")


if __name__ == '__main__':
    main()
