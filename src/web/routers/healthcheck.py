import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.web.core.logging import rq_log_error, rq_log_info
from src.web.services.engine import engine_health_check
from src.web.services.resources import rs_health_check

router = APIRouter()

@router.get("/api/v1/health")
async def health_check(request: Request):
    t1 = time.perf_counter()
    errors = {}
    try:
        engine_health_check()
    except Exception as e:
        # print(traceback.format_exc())
        errors["engine"] = str(e)
        rq_log_error(request, f'Engine health check failed: {e}')

    try:
        rs_health_check()
    except Exception as e:
        # print(traceback.format_exc())
        errors["resources"] = str(e)
        rq_log_error(request, f'Resources health check failed: {e}')

    t2 = time.perf_counter()

    if errors:
        return JSONResponse({"message":"Health check failed", "errors": errors}, status_code=500)
    rq_log_info(request, f'Health check succeeded, Time = {(t2 - t1):.06f} seconds')
    return JSONResponse({"status": "healthy"}, status_code=200)
