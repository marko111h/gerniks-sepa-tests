import pytest
import requests
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the CashControl dev API."""
    url = os.getenv("BASE_URL")
    assert url, "BASE_URL not set in .env"
    return url


@pytest.fixture(scope="session")
def auth_headers():
    """Authorization headers with Bearer token + API Key."""
    token = os.getenv("BEARER_TOKEN")
    api_key = os.getenv("API_KEY")
    assert token, "BEARER_TOKEN not set in .env"
    assert api_key, "API_KEY not set in .env"
    return {
        "Authorization": f"Bearer {token}",
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@pytest.fixture(scope="session")
def entity_id():
    """Entity ID for the test environment."""
    return os.getenv("ENTITY_ID", "MarkoGym1")


@pytest.fixture(scope="session")
def api(base_url, auth_headers):
    """
    Pre-configured requests session with auth headers.
    Use this fixture in tests instead of raw requests.
    """
    session = requests.Session()
    session.headers.update(auth_headers)
    session.base_url = base_url
    yield session
    session.close()