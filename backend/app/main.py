from fastapi import FastAPI

app = FastAPI(title="JEV Jornada")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
