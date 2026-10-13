import logging

from src.config.constants import ENGINE_LOGGER_NAME

# The logger has been set up by master
logger = logging.getLogger(ENGINE_LOGGER_NAME)

del ENGINE_LOGGER_NAME
del logging
