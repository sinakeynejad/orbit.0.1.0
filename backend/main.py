"""Development entry point: python main.py from backend/."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000)
