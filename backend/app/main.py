import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database.connection import init_db, check_db_connection
from app.api.health import router as health_router
from app.api.system import router as system_router
from app.api.documents import router as documents_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.chat import router as chat_router
from app.api.rag import router as rag_router
from app.api.llm import router as llm_router
from app.api.evaluation import router as evaluation_router

# Configure application logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("enterprise_rag.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for application startup and shutdown."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Documents directory initialized at: {settings.DOCUMENTS_DIR}")
    logger.info(f"Vector store directory initialized at: {settings.VECTORSTORE_DIR}")
    logger.info(f"Allowed CORS origins: {settings.CORS_ORIGINS}")

    # Initialize database tables
    try:
        init_db()
    except Exception as exc:
        logger.warning(f"Database initialization note: {exc}")

    # Load persistent FAISS vector store if available on disk
    try:
        from app.rag.vector_store import vector_store
        loaded = vector_store.load_index()
        if loaded:
            logger.info(f"Loaded existing FAISS vector index with {vector_store.total_vectors} vectors.")
        else:
            logger.info("No pre-existing FAISS vector index found on disk. Ready for building.")
    except Exception as exc:
        logger.warning(f"Note loading FAISS index on startup: {exc}")

    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing & logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


# Global Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "status_code": exc.status_code,
            "error": exc.detail,
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_details = []
    for err in errors:
        loc = " -> ".join([str(l) for l in err.get("loc", [])])
        msg = err.get("msg", "Invalid parameter")
        error_details.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "status_code": 422,
            "error": "Validation error",
            "details": error_details,
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "status_code": 500,
            "error": "Internal server error occurred.",
            "path": request.url.path,
        },
    )


# Include API Routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(knowledge_base_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    """Root entrypoint providing service metadata and API explorer links."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_check": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
