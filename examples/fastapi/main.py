import observo
from fastapi import FastAPI

app = FastAPI()

observo.set_password("1234")
observo.watch_logs()
observo_asgi_app = observo.get_asgi_app()

app.mount("/observo", observo_asgi_app)


@app.get("/")
async def index():
    return "Hello, World!"
