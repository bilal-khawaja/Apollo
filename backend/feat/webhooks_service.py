import os
from enum import Enum

N8N_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

# Map node paths cleanly in an Enum
class N8nEndpoints(str, Enum):
    LOW_STOCK = "fire_email_service"
    FILE_GENERATION = "generate_sheet"
    SECURITY_ALERT = "admin_alert"

def get_n8n_url(endpoint: N8nEndpoints) -> str:
    return f"{N8N_BASE_URL.rstrip('/')}/{endpoint.value}"