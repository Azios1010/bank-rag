from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Digital Expert Agents API"
    app_version: str = "1.0.0"
    environment: str = "development"
    app_debug: bool = False
    auth_mode: str = "demo"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_jwks_url: str | None = None
    policy_admin_roles: list[str] = Field(default_factory=lambda: ["policy_admin"])
    case_admin_roles: list[str] = Field(default_factory=lambda: ["case_admin"])
    enable_mock_apis: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/"
        "digital_expert_agents"
    )
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    minio_url: str = "http://localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_case_bucket: str = "case-documents"
    minio_policy_bucket: str = "bank-policies"
    minio_secure: bool = False
    max_upload_bytes: int = 20 * 1024 * 1024
    allowed_upload_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/json",
            "text/plain",
        ]
    )

    embedding_provider: str = "openai_compatible"
    embedding_api_base: str | None = "https://mkp-api.fptcloud.com"
    embedding_api_key: SecretStr | None = None
    embedding_dimension: int = 1024
    embedding_model: str = "Vietnamese_Embedding"
    llm_provider: str = "openai_compatible"
    llm_api_base: str | None = "https://mkp-api.fptcloud.com"
    llm_api_key: SecretStr | None = None
    llm_model: str = "GLM-5.2"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4_096
    agent_document_context_chars: int = 60_000

    workflow_definition: Path = BACKEND_DIR / "app/workflows/definitions/corporate_loan_v1.yaml"
    max_debate_rounds: int = 3
    seed_demo_policies: bool = False
    seed_demo_case: bool = True
    seed_hhb_policy: bool = True
    hhb_policy_path: Path = BACKEND_DIR / "resources/policies/QD-HHB-2026-01.txt"
    demo_officer_id: str = "demo-officer"
    demo_case_document_path: Path = (
        BACKEND_DIR / "resources/demo/minh-an-credit-dossier.txt"
    )
    policy_admin_officer_ids: list[str] = Field(
        default_factory=lambda: ["demo-officer"]
    )
    mock_shb_base_url: str = "http://127.0.0.1:8000/api/v1/mock-shb"
    mock_shb_timeout_seconds: float = 5.0

    @model_validator(mode="after")
    def validate_ai_configuration(self) -> "Settings":
        if self.embedding_dimension != 1024:
            raise ValueError("EMBEDDING_DIMENSION must remain 1024 for this schema")
        if self.embedding_provider not in {"deterministic_test", "openai_compatible"}:
            raise ValueError(
                "EMBEDDING_PROVIDER must be deterministic_test or openai_compatible"
            )
        if self.embedding_provider == "deterministic_test" and self.environment != "test":
            raise ValueError(
                "deterministic_test embeddings are restricted to the test environment"
            )
        if self.llm_provider != "openai_compatible":
            raise ValueError("LLM_PROVIDER must be openai_compatible")
        if self.max_debate_rounds < 1:
            raise ValueError("MAX_DEBATE_ROUNDS must be at least 1")
        if not 0 <= self.llm_temperature <= 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        if self.agent_document_context_chars < 1_000:
            raise ValueError("AGENT_DOCUMENT_CONTEXT_CHARS must be at least 1000")
        if self.auth_mode not in {"demo", "jwt"}:
            raise ValueError("AUTH_MODE must be demo or jwt")
        if self.auth_mode == "demo" and self.environment not in {
            "development",
            "test",
        }:
            raise ValueError("Demo header authentication is forbidden outside dev/test")
        if self.auth_mode == "jwt" and not all(
            (self.jwt_issuer, self.jwt_audience, self.jwt_jwks_url)
        ):
            raise ValueError("JWT issuer, audience, and JWKS URL are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
