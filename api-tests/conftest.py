import pytest
import requests
import os
from faker import Faker
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

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


@pytest.fixture(scope="session")
def db():
    """PostgreSQL database connection for test verification."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def get_internal_tx_id(db):
    """Helper to get internal transaction ID by external ID."""
    def _get(ext_id: str) -> int:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, status_cd, due_date
                FROM app.pm_transaction
                WHERE id_ext_transaction = %s
                LIMIT 1
                """,
                (ext_id,)
            )
            row = cur.fetchone()
            return row if row else None
    return _get