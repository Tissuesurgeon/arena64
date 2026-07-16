"""Alibaba Cloud Model Studio endpoint helpers (from Voya)."""

from __future__ import annotations

DEFAULT_INTL_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

WORKSPACE_SCOPED_REGIONS = frozenset(
    {
        "ap-southeast-1",
        "cn-beijing",
        "eu-central-1",
        "ap-northeast-1",
    }
)

SHARED_ENDPOINT_REGIONS = {
    "us-east-1": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
    "cn-beijing-legacy": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def build_model_studio_base_url(workspace_id: str, region: str) -> str:
    ws = workspace_id.strip()
    if not ws:
        raise ValueError("MODEL_STUDIO_WORKSPACE_ID is required for workspace-scoped regions")
    region = region.strip()
    if region not in WORKSPACE_SCOPED_REGIONS:
        raise ValueError(f"Unsupported Model Studio region: {region}")
    return f"https://{ws}.{region}.maas.aliyuncs.com/compatible-mode/v1"


def resolve_qwen_base_url(
    *,
    explicit_base_url: str,
    workspace_id: str,
    region: str,
) -> str:
    explicit = (explicit_base_url or "").strip().rstrip("/")
    ws = (workspace_id or "").strip()
    reg = (region or "ap-southeast-1").strip()

    if ws:
        return build_model_studio_base_url(ws, reg)

    if explicit and explicit != DEFAULT_INTL_BASE_URL.rstrip("/"):
        return explicit

    shared = SHARED_ENDPOINT_REGIONS.get(reg)
    if shared:
        return shared.rstrip("/")

    return explicit or DEFAULT_INTL_BASE_URL.rstrip("/")
