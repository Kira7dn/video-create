"""
Application entry point
"""

if __name__ == "__main__":
    import uvicorn
    from app.main import app
    from app.config.settings import settings

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
