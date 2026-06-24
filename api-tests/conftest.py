import pytest
import requests
import os
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker("de_DE")

BASE_URL = os.getenv("BASE_URL", "https://dev-cc.dev.gerniks.net")
API_KEY = os.getenv("API_KEY")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

HEADERS = {
    "API-key": API_KEY,
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def headers():
    return HEADERS


@pytest.fixture(scope="session")
def api(base_url, headers):
    """Pre-configured requests session."""
    session = requests.Session()
    session.headers.update(headers)
    session.base_url = base_url
    yield session
    session.close()


@pytest.fixture
def new_consumer(api, base_url):
    """Creates a fresh consumer and returns its data."""
    from utils.iban_utils import valid_bank_information
    first = fake.first_name()
    last = fake.last_name()

    r = api.post(
        f"{base_url}/api/public/p2/v1/consumer",
        json=[{
            "idExternal": fake.uuid4(),
            "firstName": first,
            "lastName": last,
            "type": "PERSON",
            "flgDunningEnabled": "true",
            "gender": "MALE",
            "email": fake.email(),
            "bankAccounts": valid_bank_information(f"{first} {last}")
        }]
    )
    assert r.status_code == 201, \
        f"Failed to create consumer: {r.status_code} {r.text}"
    return r.json()[0]