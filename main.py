from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from dotenv import load_dotenv
# from fastapi.staticfiles import StaticFiles

from Routes.model_route import router as model_router
from Routes.memory_route import router as memory_router
from Routes.user_route import router as user_router
from Routes.write_file_route import router as write_file_router
from Routes.read_file_route import router as read_file_router
from Database import pg


load_dotenv()

app = FastAPI(
    title="MemoAR Backend",
    version="0.1.0",
)


@app.middleware("http")
async def log_api_process(request: Request, call_next):
    request_id = str(uuid4())
    started = perf_counter()
    response = None
    error = None

    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        error = exc
        raise
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        status_code = getattr(response, "status_code", None)

        process_status = "success"
        error_type = None
        error_message = None

        if error is not None:
            process_status = "error"
            status_code = getattr(error, "status_code", None) or 500
            error_type = type(error).__name__
            error_message = str(error)
        elif status_code is not None and status_code >= 400:
            process_status = "error"
            error_type = "HTTPError"
            error_message = f"HTTP {status_code}"

        try:
            pg.insert_api_process_record(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "route_path": route_path,
                    "query_string": request.url.query or None,
                    "status_code": status_code,
                    "process_status": process_status,
                    "error_type": error_type,
                    "error_message": error_message,
                    "duration_ms": duration_ms,
                    "client_host": request.client.host if request.client else None,
                    "request_meta": {
                        "path_params": dict(request.path_params),
                        "query_params": dict(request.query_params),
                        "client_request_id": request.headers.get("x-memoar-client-request-id"),
                        "client_api_name": request.headers.get("x-memoar-client-api-name"),
                    },
                }
            )
        except Exception as logging_error:
            print("⚠️ api process log skipped:", repr(logging_error))

@app.on_event("startup")
def _startup_migrate():
    try:
        pg.migrate()
    except Exception as e:
        message = str(e)
        if "SUPABASE_DATABASE_URL" in message or "SUPABASE_DB_URL" in message:
            print(
                "⚠️ notification_records migrate skipped: "
                "set SUPABASE_DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string."
            )
        print("⚠️ migrate skipped:", repr(e))

app.include_router(model_router)
app.include_router(memory_router)
app.include_router(user_router)
app.include_router(write_file_router)
app.include_router(read_file_router)

# expose Storage directory
# app.mount("/Storage", StaticFiles(directory="Storage"), name="Storage")


@app.get("/")
def health_check():
    return {"status": "MemoAR backend running"}
