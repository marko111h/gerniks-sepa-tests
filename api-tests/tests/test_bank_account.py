import pytest
from faker import Faker
from utils.iban_utils import generate_valid_german_iban

fake = Faker("de_DE")


class TestBankAccountGet:
    """GET /api/public/p2/v1/consumer/{consumerId}/bank-account"""

    @pytest.mark.sepa
    def test_get_bank_accounts_returns_200(self, api, base_url, new_consumer):
        """GET bank accounts for consumer returns 200."""
        consumer_id = new_consumer["id"]
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}/bank-account"
        )
        assert r.status_code == 200, \
            f"Expected 200, got {r.status_code}: {r.text}"

    @pytest.mark.sepa
    def test_consumer_created_with_bank_account_has_one(
            self, api, base_url, new_consumer):
        """Consumer created with bank account has at least one account."""
        consumer_id = new_consumer["id"]
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}/bank-account"
        )
        assert r.status_code == 200
        data = r.json()

        # Response can be array or paginated
        accounts = data.get("content", data) if isinstance(data, dict) else data
        assert len(accounts) > 0, "Consumer should have at least one bank account"
        print(f"\n✅ Consumer has {len(accounts)} bank account(s)")

    @pytest.mark.sepa
    def test_bank_account_has_required_fields(
            self, api, base_url, new_consumer):
        """Bank account has required fields."""
        consumer_id = new_consumer["id"]
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}/bank-account"
        )
        assert r.status_code == 200
        data = r.json()
        accounts = data.get("content", data) if isinstance(data, dict) else data

        if len(accounts) == 0:
            pytest.skip("No bank accounts found")

        account = accounts[0]
        assert "id" in account, "Bank account missing 'id'"
        assert "iban" in account, "Bank account missing 'iban'"
        print(f"\n✅ Bank account fields: {list(account.keys())}")

    @pytest.mark.sepa
    def test_get_bank_account_by_id(self, api, base_url, new_consumer):
        """GET bank account by ID returns correct account."""
        consumer_id = new_consumer["id"]

        # Get list first
        r_list = api.get(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}/bank-account"
        )
        assert r_list.status_code == 200
        data = r_list.json()
        accounts = data.get("content", data) if isinstance(data, dict) else data

        if len(accounts) == 0:
            pytest.skip("No bank accounts found")

        account_id = accounts[0]["id"]

        # Get by ID
        r = api.get(
            f"{base_url}/api/public/p2/v1/consumer/"
            f"{consumer_id}/bank-account/{account_id}"
        )
        assert r.status_code == 200
        assert r.json()["id"] == account_id
        print(f"\n✅ Bank account by ID: {account_id}")


class TestBankAccountCreate:
    """POST /api/public/p2/v1/consumer/{consumerId}/bank-account"""

    @pytest.mark.sepa
    def test_add_bank_account_to_consumer(self, api, base_url, new_consumer):
        """Add new bank account to existing consumer."""
        consumer_id = new_consumer["id"]
        full_name = (
            f"{new_consumer.get('firstName', '')} "
            f"{new_consumer.get('lastName', '')}"
        ).strip()

        iban = generate_valid_german_iban()

        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer/"
            f"{consumer_id}/bank-account",
            json=[{
                "iban": iban,
                "bic": "COBADEFFXXX",
                "owner": full_name,
                "bankName": "Commerzbank AG",
                "flgPrimaty": False,
                "flgConsumer360": True,
                "flgVerify": True,
            }]
        )
        assert r.status_code in [200, 201], \
            f"Expected 200/201, got {r.status_code}: {r.text}"
        print(f"\n✅ Bank account added: {iban}")

    @pytest.mark.sepa
    def test_add_invalid_iban_rejected(self, api, base_url, new_consumer):
        """Adding invalid IBAN to consumer is rejected."""
        consumer_id = new_consumer["id"]

        r = api.post(
            f"{base_url}/api/public/p2/v1/consumer/"
            f"{consumer_id}/bank-account",
            json=[{
                "iban": "NOT_A_VALID_IBAN",
                "bic": "COBADEFFXXX",
                "owner": "Test Owner",
                "flgPrimaty": False,
            }]
        )
        assert r.status_code in [400, 422], \
            f"Expected 400/422 for invalid IBAN, got {r.status_code}: {r.text}"
        print(f"\n✅ Invalid IBAN rejected: {r.status_code}")


class TestBankAccountUpdate:
    """PUT /api/public/p2/v1/consumer/{consumerId}/bank-account/{id}"""

    @pytest.mark.sepa
    def test_set_bank_account_as_primary(self, api, base_url, new_consumer):
        """Set bank account as primary."""
        consumer_id = new_consumer["id"]

        # Get existing accounts
        r_list = api.get(
            f"{base_url}/api/public/p2/v1/consumer/{consumer_id}/bank-account"
        )
        assert r_list.status_code == 200
        data = r_list.json()
        accounts = data.get("content", data) if isinstance(data, dict) else data

        if len(accounts) == 0:
            pytest.skip("No bank accounts found")

        account_id = accounts[0]["id"]

        # Set as primary
        r = api.put(
            f"{base_url}/api/public/p2/v1/consumer/"
            f"{consumer_id}/bank-account/{account_id}/primary"
        )
        assert r.status_code in [200, 204], \
            f"Expected 200/204, got {r.status_code}: {r.text}"
        print(f"\n✅ Bank account set as primary: {account_id}")