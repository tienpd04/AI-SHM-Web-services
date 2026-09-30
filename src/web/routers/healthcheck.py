import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.config.settings import RESOURCES_MANAGER_LOG_INTERVAL
from src.shared import current_using_shms, overwrite_counter
from src.web.core.logging import logger, rq_log_error, rq_log_info
from src.web.services.engine import engine_health_check

router = APIRouter()


@router.get("/api/v1/health")
async def health_check(request: Request):

    t1 = time.perf_counter()
    now = time.time()

    if int(RESOURCES_MANAGER_LOG_INTERVAL) > 0 and (int(now) % int(RESOURCES_MANAGER_LOG_INTERVAL)) // 30 == 0:
        # Doesn't need to be perfectly precise;
        # 30: health check configured in docker-compose
        try:
            logger.info(
                "[Interval Log] Current using resources: %s", current_using_shms())
            logger.info("[Interval Log] Number of times shared memory was overwritten: %d",
                        overwrite_counter.get_value())
        except Exception as e:
            logger.warning("Error while logging current resources: %s", {e})

    errors = {}
    try:
        engine_health_check()
    except Exception as e:
        # print(traceback.format_exc())
        errors["engine"] = str(e)
        rq_log_error(request, f'Engine health check failed: {e}')

    t2 = time.perf_counter()

    if errors:
        return JSONResponse({"message": "Health check failed", "errors": errors}, status_code=500)
    rq_log_info(
        request, f'Health check succeeded, Time = {(t2 - t1):.06f} seconds')
    return JSONResponse({"status": "healthy"}, status_code=200)
