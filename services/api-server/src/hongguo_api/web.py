"""Serve the built React application without changing API route semantics."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

WEB_DIST = Path(__file__).with_name("web_dist")


def install_web(app: FastAPI, web_dist: Path) -> None:
    """Install explicit web entry routes and hashed static assets."""

    index_file = web_dist / "index.html"
    assets_dir = web_dist / "assets"

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

    async def web_entry() -> Response:
        if not index_file.is_file():
            return JSONResponse(
                status_code=503,
                content={
                    "code": "web_build_missing",
                    "message": (
                        "Run npm install and npm run build in services/api-server/web"
                    ),
                },
            )
        return FileResponse(index_file)

    for path in ("/", "/docs", "/pricing"):
        app.add_api_route(path, web_entry, methods=["GET"], include_in_schema=False)
