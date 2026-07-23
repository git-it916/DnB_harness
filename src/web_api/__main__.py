import os

import uvicorn


def main() -> None:
    port = int(os.getenv("DNB_PORT", "8000"))
    uvicorn.run("src.web_api.app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
