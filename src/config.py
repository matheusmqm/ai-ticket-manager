"""Configuração lida de variáveis de ambiente / .env. Nenhum segredo no código."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jira_base_url: str
    jira_email: str
    jira_api_token: SecretStr
    jira_project_key: str = "ID"
    jira_issue_type: str = "Ticket"

    # Opcional: sobrescreve a descoberta automática dos campos personalizados.
    jira_field_area: str | None = None
    jira_field_categoria: str | None = None
    jira_field_decisao: str | None = None

    # Planilha pública de pedidos, exportada como CSV (consulta de pedidos).
    planilha_pedidos_url: str = (
        "https://docs.google.com/spreadsheets/d/13k_6nbk02ZDlfINyuNAUfPAnaojFuPvOLetMyoMbKxI/export?format=csv"
    )

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-haiku-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
