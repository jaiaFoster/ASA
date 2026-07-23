from fastapi import FastAPI

from asa.bootstrap import build_application
from asa.config import Settings


def create_application() -> FastAPI:
    """Create the ASGI application through the single production composition root."""
    return build_application(Settings())
