import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"🚀 Launching AeroSOP AI Weather Advisory Server at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
