import os
from dotenv import load_dotenv

load_dotenv()


def get_subsription_headers():
    key = os.environ.get("PJM_SUBSCRIPTION_KEY")
    if not key:
        raise RuntimeError("PJM_SUBSCRIPTION_KEY environment variable is not set. Add it to your .env file.")
    return {"Ocp-Apim-Subscription-Key": key}
