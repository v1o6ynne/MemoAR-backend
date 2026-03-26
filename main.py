from fastapi import FastAPI
from dotenv import load_dotenv
# from fastapi.staticfiles import StaticFiles

from Routes.model_route import router as model_router
from Routes.memory_route import router as memory_router
from Routes.write_file_route import router as write_file_router
from Routes.read_file_route import router as read_file_router


load_dotenv()

app = FastAPI(
    title="MemoAR Backend",
    version="0.1.0",
)

@app.on_event("startup")
def _startup_migrate():
    # Safe: CREATE TABLE IF NOT EXISTS
    migrate()



app.include_router(model_router)
app.include_router(memory_router)
app.include_router(write_file_router)
app.include_router(read_file_router)

# expose Storage directory
# app.mount("/Storage", StaticFiles(directory="Storage"), name="Storage")


@app.get("/")
def health_check():
    return {"status": "MemoAR backend running"}
