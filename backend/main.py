"""API do painel: proxy fino entre o React e o Jira (o Jira bloqueia CORS e o token não vai para o navegador).

Uso (na raiz do projeto):
    uv run uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.deps import fechar_jira
from backend.routers import chamados, metricas

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    fechar_jira()


app = FastAPI(title="Painel de chamados", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(chamados.router)
app.include_router(metricas.router)
