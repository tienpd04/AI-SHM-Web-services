

import secrets

_module_key = secrets.token_hex(8)
del secrets


def _create_app():
    import os

    from fastapi import FastAPI

    from src.web.core.logging import logger
    from src.web.middleware.request_id import SetRequestIDMiddleware
    from src.web.routers import api_router

    app = FastAPI(access=False)
    logger.info("Check differences from the worker module. Worker PID: %d, module key: %s",
                os.getpid(), _module_key)
    app.add_middleware(SetRequestIDMiddleware)
    app.include_router(api_router)

    return app


app = _create_app()

del _create_app
