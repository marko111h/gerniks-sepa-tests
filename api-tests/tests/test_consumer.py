import pytest
from faker import Faker
from utils.iban_utils import valid_bank_information

fake = Faker("de_DE")


class TestConsumerGet:
    """GET /api/public/p2/v1/consumer"""

    @pytest.mark.smoke
    @pytest.mark.sepa
    def test_get_consumers_returns_200(self, api, base_url):
        """GET consumers returns 200 OK."""
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer",
            params={"page": 0, "size": 10}
        )
        assert r.status_code == 200

    @pytest.mark.sepa
    def test_get_consumers_pagination_structure(self, api, base_url):
        """Response has Spring Boot pagination fields."""
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer",
            params={"page": 0, "size": 5}
        )
        assert r.status_code == 200
        data = r.json()
        assert "content" in data
        assert "totalElements" in data
        assert "totalPages" in data
        assert isinstance(data["content"], list)

    @pytest.mark.sepa
    def test_get_consumer_by_id(self, api, base_url, new_consumer):
        """GET consumer by ID returns correct consumer."""
        consumer_id = new_consumer["id"]
        r = api.get(f"{base_url}/api/public/p2/v1/consumer/{consumer_id}")
        assert r.status_code == 200
        assert r.json()["id"] == consumer_id

    @pytest.mark.sepa
    def test_get_nonexistent_consumer(self, api, base_url):
        """GET non-existing consumer returns 403 or 404."""
        r = api.get(f"{base_url}/api/public/p2/v1/consumer/99999999")
        assert r.status_code in [403, 404], \
            f"Expected 403/404, got {r.status_code}"


class TestConsumerCreate:
    """POST /api/public/p2/v1/consumer"""

    @pytest.mark.sepa
    def test_create_person_consumer(self, api, base_url):
        """Creates a PERSON consumer with bank account."""
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
            f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()[0]
        assert data["firstName"] == first
        assert data["lastName"] == last
        assert data["status"] == "ACTIVE"
        assert len(data.get("bankAccounts", [])) > 0, \
            "BUG: bankAccount not created!"
        print(f"\n✅ Consumer created: {first} {last}")

    @pytest.mark.sepa
    def test_create_consumer_missing_firstname(self, api, base_url):
        """POST without firstName returns validation error."""
        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer",
            json=[{
                "idExternal": fake.uuid4(),
                "lastName": "TestLast",
                "type": "PERSON",
                "email": fake.email()
            }]
        )
        assert r.status_code in [400, 422], \
            f"Expected 400/422, got {r.status_code}"

    @pytest.mark.sepa
    def test_create_consumer_invalid_iban(self, api, base_url):
        """Invalid IBAN should be rejected with 400."""
        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer",
            json=[{
                "idExternal": fake.uuid4(),
                "firstName": fake.first_name(),
                "lastName": fake.last_name(),
                "type": "PERSON",
                "email": fake.email(),
                "bankAccounts": [{
                    "iban": "INVALID_IBAN",
                    "owner": fake.name()
                }]
            }]
        )
        assert r.status_code == 400, \
            f"Expected 400 for invalid IBAN, got {r.status_code}"
        print("\n✅ Invalid IBAN correctly rejected with 400")

    @pytest.mark.sepa
    def test_create_company_consumer(self, api, base_url):
        """Creates a COMPANY consumer."""
        company = fake.company()

        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer",
            json=[{
                "idExternal": fake.uuid4(),
                "companyName": company,
                "type": "COMPANY",
                "flgDunningEnabled": "true",
                "email": fake.email(),
                "bankAccounts": valid_bank_information(company)
            }]
        )
        assert r.status_code == 201, \
            f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()[0]
        assert data["status"] == "ACTIVE"
        print(f"\n✅ Company consumer created: {company}")

    @pytest.mark.sepa
    def test_bulk_create_5_consumers(self, api, base_url):
        """POST with 5 consumers in one call."""
        payload = [
            {
                "idExternal": fake.uuid4(),
                "firstName": fake.first_name(),
                "lastName": fake.last_name(),
                "type": "PERSON",
                "email": fake.email()
            }
            for _ in range(5)
        ]
        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer",
            json=payload
        )
        assert r.status_code == 201
        assert len(r.json()) == 5
        print("\n✅ Bulk create — all 5 created!")


class TestConsumerUpdate:
    """PUT /api/public/p2/v1/consumer/{id}"""

    @pytest.mark.sepa
    def test_update_consumer_name(self, api, base_url, new_consumer):
        """Update consumer first/last name."""
        consumer_id = new_consumer["id"]
        new_first = fake.first_name()
        new_last = fake.last_name()

        r = api.put(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}",
            json={
                "firstName": new_first,
                "lastName": new_last,
                "typeCd": "PERSON",
                "email": fake.email()
            }
        )
        assert r.status_code == 200, \
            f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["firstName"] == new_first
        print(f"\n✅ Consumer updated: {new_first} {new_last}")