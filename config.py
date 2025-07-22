import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# === Exception for Missing Required Configs ===
class ConfigError(Exception):
    pass

# === Azure Key Vault Setup (lazy initialization) ===
_keyvault_client = None

def get_from_secret_manager(var_name: str) -> str:
    """
    Attempts to retrieve a secret from Azure Key Vault.
    Returns None if Key Vault is not available or the secret is not found.
    """
    global _keyvault_client
    try:
        vault_url = os.getenv("AZURE_KEYVAULT_URL")
        if not vault_url:
            return None  # Key Vault not configured

        if not _keyvault_client:
            credential = DefaultAzureCredential()
            _keyvault_client = SecretClient(vault_url=vault_url, credential=credential)

        secret = _keyvault_client.get_secret(var_name)
        return secret.value
    except Exception:
        return None  # Gracefully fallback to env

def get_env(var_name: str, required: bool = True, default: str = None) -> str:
    """
    Retrieves a configuration value in the following priority:
    1. Azure Key Vault (if configured)
    2. Environment variable (.env or Streamlit secrets)
    3. Default (if provided)
    """
    value = None

    # Priority 1: Azure Key Vault (only if ENV=production or AZURE_KEYVAULT_URL set)
    if os.getenv("ENV", "").lower() == "production" or os.getenv("AZURE_KEYVAULT_URL"):
        value = get_from_secret_manager(var_name)

    # Priority 2: Environment fallback
    if value is None:
        value = os.getenv(var_name, default)

    # Enforce required check
    if required and not value:
        raise ConfigError(f"Missing required environment variable: {var_name}")

    return value

# === Centralized Configuration Loader ===
class AppConfig:
    def __init__(self):
        # === OpenAI ===
        self.OPENAI_API_KEY = get_env("OPENAI_API_KEY")

        # === Microsoft Graph ===
        self.GRAPH_CLIENT_ID = get_env("GRAPH_CLIENT_ID")
        self.GRAPH_CLIENT_SECRET = get_env("GRAPH_CLIENT_SECRET")
        self.GRAPH_TENANT_ID = get_env("GRAPH_TENANT_ID")
        self.GRAPH_SENDER_EMAIL = get_env("GRAPH_SENDER_EMAIL")

        # === NEOS ===
        self.NEOS_API_KEY = get_env("NEOS_API_KEY")
        self.NEOS_BASE_URL = get_env("NEOS_BASE_URL", default="https://app.neosconnect.com/api/v1")
        self.NEOS_COMPANY_ID = get_env("NEOS_COMPANY_ID")

        # === Dropbox ===
        self.DROPBOX_APP_KEY = get_env("DROPBOX_APP_KEY")
        self.DROPBOX_APP_SECRET = get_env("DROPBOX_APP_SECRET")
        self.DROPBOX_REFRESH_TOKEN = get_env("DROPBOX_REFRESH_TOKEN")
        self.DROPBOX_MASTER_DASHBOARD_PATH = get_env("DROPBOX_MASTER_DASHBOARD_PATH", default="/Master Dashboard.xlsx")

# === Accessor ===
def get_config() -> AppConfig:
    return AppConfig()
