"""Packaged, build-free read-only ASA intelligence interface."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIRECTORY = Path(__file__).with_name("static")
_INDEX = _STATIC_DIRECTORY / "index.html"


def mount_ui(app: FastAPI) -> None:
    """Mount Slice 1 static assets without adding an application data boundary."""

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    def ui_shell() -> FileResponse:
        return FileResponse(_INDEX)

    app.mount(
        "/ui/static",
        StaticFiles(directory=_STATIC_DIRECTORY),
        name="asa-ui-static",
    )


__all__ = ["mount_ui"]
