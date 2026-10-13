SHM_HEADER_SIZE = 16

MAIN_LOGGER_NAME = 'main'

FASTAPI_LOGGER_NAME = 'fastapi'

ENGINE_LOGGER_NAME = 'engine'

__all__ = [x for x in locals() if not x.startswith('_')]