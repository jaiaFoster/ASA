import uvicorn

from asa.bootstrap import build_application
from asa.config import Settings

if __name__ == "__main__":
    uvicorn.run(build_application(Settings()), host="0.0.0.0", port=8000)
