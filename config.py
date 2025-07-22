import os

class ConfigError(Exception):
    pass

def get_from_secret_manager(var_name: str) -> str:
    """
    Optional: override this stub with Azure Key Vault, AWS Secrets Manager, etc.
    Return None if secret not found in vault.
    """
    # Placeholder logic – customize as needed
    return None  # Integrate Azure SDK or boto3 here for actual vault access


def get_env(var_name: str, required: bool = True, default: str = None) -> str:
    """
    Retrieves environment variable with support for secret manager override.
    Priority: Secret Vault > os.environ > Default
    """
    value = None

    # 1. Secret Vault (for production)
    if os.getenv("ENV", "").lower() == "production":
        value = get_from_secret_manager(var_name)

    # 2. Environment fallback
    if value is None:
        value = os.getenv(var_name, default)

    if required and not value:
        raise ConfigError(f"Missing required environment variable: {var_name}")
    
    return value


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

def get_config() -> AppConfig:
    return AppConfig()
