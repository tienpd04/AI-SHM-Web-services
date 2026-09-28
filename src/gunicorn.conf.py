import logging
import sys


# 2. Add a custom hook to attach a stdout handler to Gunicorn's logger
def on_starting(server):
    # Get Gunicorn's error logger
    gunicorn_logger = logging.getLogger("gunicorn.error")

    # Create a StreamHandler that writes to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)

    # Optional: Reuse Gunicorn's existing formatter for consistency
    if gunicorn_logger.handlers:
        stdout_handler.setFormatter(gunicorn_logger.handlers[0].formatter)

    # Append the stdout handler so logs go to both the file and stdout
    gunicorn_logger.addHandler(stdout_handler)
