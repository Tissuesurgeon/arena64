from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load monorepo root .env, then apps/api/.env (API cwd overrides)
# config.py lives at apps/api/app/core/config.py
_CONFIG_FILE = Path(__file__).resolve()
_ROOT_ENV = _CONFIG_FILE.parents[4] / ".env"
_API_ENV = _CONFIG_FILE.parents[2] / ".env"
_ENV_FILES = tuple(str(p) for p in (_ROOT_ENV, _API_ENV) if p.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        protected_namespaces=("settings_",),
    )

    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    database_url: str = "postgresql+asyncpg://arena64:arena64@localhost:5432/arena64"
    database_url_sync: str = "postgresql://arena64:arena64@localhost:5432/arena64"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"
    service_api_key: str = "arena64-dev-service-key"

    # Injective — default testnet. Flip INJECTIVE_NETWORK=mainnet only after checklist.
    injective_network: str = Field(default="testnet", alias="INJECTIVE_NETWORK")
    injective_evm_chain_id: Optional[int] = Field(default=None, alias="INJECTIVE_EVM_CHAIN_ID")
    injective_usdc_address: Optional[str] = Field(default=None, alias="INJECTIVE_USDC_ADDRESS")
    injective_rpc_url: Optional[str] = Field(default=None, alias="INJECTIVE_RPC_URL")
    x402_facilitator_url: str = Field(default="https://x402.org/facilitator", alias="X402_FACILITATOR_URL")
    x402_network: Optional[str] = Field(default=None, alias="X402_NETWORK")
    cctp_iris_api: Optional[str] = Field(default=None, alias="CCTP_IRIS_API")
    cctp_domain: Optional[int] = Field(default=None, alias="CCTP_DOMAIN")
    cctp_require_attestation: bool = Field(default=True, alias="CCTP_REQUIRE_ATTESTATION")
    x402_require_verify: bool = Field(default=True, alias="X402_REQUIRE_VERIFY")
    # When facilitator lacks eip155:1439 support, allow recorded proof on testnet only
    x402_allow_testnet_fallback: bool = Field(default=True, alias="X402_ALLOW_TESTNET_FALLBACK")

    # Web Scout — free DuckDuckGo search → football platforms (no Wikipedia)
    scout_allowed_hosts: str = (
        "espn.com,www.espn.com,bbc.com,www.bbc.com,goal.com,www.goal.com,"
        "fifa.com,www.fifa.com,skysports.com,www.skysports.com,"
        "transfermarkt.com,www.transfermarkt.com,reuters.com,www.reuters.com,"
        "theguardian.com,www.theguardian.com,uefa.com,www.uefa.com,"
        "flashscore.com,www.flashscore.com,sofascore.com,www.sofascore.com,"
        "whoscored.com,www.whoscored.com,cbssports.com,www.cbssports.com,"
        "marca.com,www.marca.com,mlssoccer.com,www.mlssoccer.com"
    )
    scout_auto_approve: bool = Field(default=True, alias="SCOUT_AUTO_APPROVE")

    # --- LLM stack (Voya pattern): Ollama local → Qwen cloud → heuristics ---
    ai_provider: str = Field(default="auto", alias="AI_PROVIDER")

    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    qwen_base_url: str = Field(
        default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        alias="QWEN_BASE_URL",
    )
    model_studio_workspace_id: str = Field(default="", alias="MODEL_STUDIO_WORKSPACE_ID")
    model_studio_region: str = Field(default="ap-southeast-1", alias="MODEL_STUDIO_REGION")
    qwen_chat_model: str = Field(default="qwen-plus", alias="QWEN_CHAT_MODEL")

    ollama_enabled: bool = Field(default=True, alias="OLLAMA_ENABLED")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: float = Field(default=120.0, alias="OLLAMA_TIMEOUT_SECONDS")

    admin_wallets: str = ""
    # Product mode: faucet off by default — players fund with real testnet USDC
    demo_faucet_enabled: Optional[bool] = Field(default=False, alias="DEMO_FAUCET_ENABLED")
    demo_faucet_amount_usdc: float = 50.0
    arena64_treasury_address: str = Field(default="", alias="ARENA64_TREASURY_ADDRESS")
    arena64_treasury_private_key: str = Field(default="", alias="ARENA64_TREASURY_PRIVATE_KEY")
    # Testnet INJ faucet (InjFaucet.sol) — one claim per wallet; never expose to frontend
    inj_key_evm: str = Field(default="", alias="INJ_KEY_EVM")
    inj_faucet_address: str = Field(default="", alias="INJ_FAUCET_ADDRESS")
    premium_insight_cost_usdc: float = Field(default=0.05, alias="PREMIUM_INSIGHT_COST_USDC")

    scout_scheduler_enabled: bool = Field(default=True, alias="SCOUT_SCHEDULER_ENABLED")
    scout_interval_minutes: int = Field(default=360, alias="SCOUT_INTERVAL_MINUTES")
    scout_bootstrap_on_start: bool = Field(default=True, alias="SCOUT_BOOTSTRAP_ON_START")

    @model_validator(mode="after")
    def resolve_network_and_ai(self) -> "Settings":
        from app.integrations.injective.networks import get_profile
        from app.integrations.qwen.model_studio import resolve_qwen_base_url

        profile = get_profile(self.injective_network)
        self.injective_network = profile.name

        # Network profile is source of truth — flipping INJECTIVE_NETWORK
        # always syncs chain / USDC / Iris / x402 CAIP-2 (no mixed mainnet+testnet).
        self.injective_evm_chain_id = profile.evm_chain_id
        self.injective_usdc_address = profile.usdc_address
        self.x402_network = profile.x402_network
        self.cctp_iris_api = profile.cctp_iris_api
        self.cctp_domain = profile.cctp_domain
        self.injective_rpc_url = profile.rpc_url

        # Faucet: never on mainnet
        if self.injective_network == "mainnet":
            self.demo_faucet_enabled = False
            self.x402_allow_testnet_fallback = False
            self.cctp_require_attestation = True
            self.x402_require_verify = True
        elif self.demo_faucet_enabled is None:
            self.demo_faucet_enabled = profile.faucet_enabled_default

        if not self.qwen_api_key and self.dashscope_api_key:
            self.qwen_api_key = self.dashscope_api_key

        self.qwen_base_url = resolve_qwen_base_url(
            explicit_base_url=self.qwen_base_url,
            workspace_id=self.model_studio_workspace_id,
            region=self.model_studio_region,
        )

        provider = self.ai_provider.lower()
        if provider == "openai":
            self.ai_provider = "qwen"

        if self.qwen_api_key and provider == "ollama" and not self.ollama_enabled:
            self.ai_provider = "qwen"
        elif not self.ollama_enabled and provider == "ollama":
            self.ai_provider = "auto"

        return self

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def admin_wallet_set(self) -> set[str]:
        return {w.strip().lower() for w in self.admin_wallets.split(",") if w.strip()}

    @property
    def cloud_ai_provider(self) -> str:
        return "qwen" if self.ai_provider.lower() == "openai" else self.ai_provider.lower()

    @property
    def qwen_configured(self) -> bool:
        return bool(self.qwen_api_key)

    @property
    def is_mainnet(self) -> bool:
        return self.injective_network == "mainnet"


@lru_cache
def get_settings() -> Settings:
    return Settings()
