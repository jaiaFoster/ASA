import uvicorn

from asa.bootstrap import build_application
from asa.config import Settings

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(build_application(settings), host="0.0.0.0", port=settings.port)
