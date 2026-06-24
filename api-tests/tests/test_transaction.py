import pytest
from faker import Faker
from datetime import datetime, timedelta

fake = Faker("de_DE")


class TestTransactionGet:
    """GET /api/public/p2/v2/transaction"""

    @pytest.mark.smoke
    @pytest.mark.sepa
    def test_get_transactions_returns_200(self, api, base_url):
        """GET transactions returns 200 OK."""
        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={"page": 0, "size": 10}
        )
        assert r.status_code == 200, \
            f"Expected 200, got {r.status_code}: {r.text}"

    @pytest.mark.sepa
    def test_get_transactions_pagination_structure(self, api, base_url):
        """Response has Spring Boot pagination fields."""
        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={"page": 0, "size": 5}
        )
        assert r.status_code == 200
        data = r.json()
        assert "content" in data
        assert "totalElements" in data
        assert "totalPages" in data
        print(f"\nTotal transactions: {data['totalElements']}")

    @pytest.mark.sepa
    def test_get_transactions_filter_by_status(self, api, base_url):
        """Filter transactions by status."""
        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={
                "page": 0,
                "size": 5,
                "statusList": "MATCHED"
            }
        )
        assert r.status_code == 200
        data = r.json()
        transactions = data["content"]

        for tx in transactions:
            assert tx["status"] == "MATCHED", \
                f"Expected MATCHED, got {tx['status']}"

        print(f"\n✅ Filter by MATCHED: {len(transactions)} transactions")

    @pytest.mark.sepa
    def test_get_transactions_filter_by_date_range(self, api, base_url):
        """Filter transactions by due date range."""
        date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={
                "page": 0,
                "size": 5,
                "dueDateFrom": date_from,
                "dueDateTo": date_to
            }
        )
        assert r.status_code == 200
        print(f"\n✅ Date filter {date_from} → {date_to}: "
              f"{r.json()['totalElements']} transactions")

    @pytest.mark.sepa
    def test_get_transaction_by_external_id(self, api, base_url):
        """GET transaction by external ID."""
        r_list = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={"page": 0, "size": 1}
        )
        assert r_list.status_code == 200
        transactions = r_list.json()["content"]

        if len(transactions) == 0:
            pytest.skip("No transactions in dev environment")

        tx = transactions[0]
        ext_id = tx.get("idExternal")

        if not ext_id:
            pytest.skip("Transaction has no idExternal field")

        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction/external/{ext_id}"
        )
        assert r.status_code == 200, \
            f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["idExternal"] == ext_id
        print(f"\n✅ Transaction by external ID: {ext_id}")

    @pytest.mark.sepa
    def test_get_transactions_by_consumer(self, api, base_url, new_consumer):
        """Filter transactions by consumer external ID."""
        consumer = new_consumer
        ext_consumer_id = consumer.get("idExternal")

        if not ext_consumer_id:
            pytest.skip("Consumer has no idExternal")

        r = api.get(
            f"{base_url}/api/public/p2/v2/transaction",
            params={
                "page": 0,
                "size": 10,
                "idExtConsumer": ext_consumer_id
            }
        )
        assert r.status_code == 200
        print(f"\n✅ Transactions for consumer {ext_consumer_id}: "
              f"{r.json()['totalElements']}")


class TestTransactionCreate:
    """POST /api/public/p2/v2/transaction"""

    @pytest.mark.sepa
    def test_create_transaction_for_consumer(
            self, api, base_url, new_consumer):
        """Create a SEPA Direct Debit transaction using idConsumer."""
        consumer_id = new_consumer["id"]
        due_date = (
            datetime.now() + timedelta(days=30)
        ).strftime("%Y-%m-%d")

        r = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": fake.uuid4(),
                "idConsumer": consumer_id,
                "amount": 10.00,
                "dueDate": due_date,
                "description": "SEPA Test Transaction - pytest",
                "collectionType": "DIRECT_DEBIT"
            }]
        )

        print(f"\nPOST /transaction → {r.status_code}: {r.text[:300]}")

        if r.status_code == 403:
            pytest.skip(
                "POST /transaction returns 403 — "
                "current API key may not have write permission."
            )

        assert r.status_code in [200, 201], \
            f"Expected 200/201, got {r.status_code}: {r.text}"

        data = r.json()
        if isinstance(data, list):
            tx = data[0]
        else:
            tx = data

        assert tx["idConsumer"] == consumer_id
        assert float(tx["amount"]) == 10.00
        print(f"\n✅ Transaction created for consumer {consumer_id}")

    @pytest.mark.sepa
    def test_create_transaction_negative_amount(
            self, api, base_url, new_consumer):
        """Negative amount is rejected with 400."""
        consumer_id = new_consumer["id"]
        due_date = (
            datetime.now() + timedelta(days=30)
        ).strftime("%Y-%m-%d")

        r = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": fake.uuid4(),
                "idConsumer": consumer_id,
                "amount": -50.00,
                "dueDate": due_date,
                "collectionType": "DIRECT_DEBIT"
            }]
        )
        if r.status_code == 403:
            pytest.skip("No write permission for transactions")
        assert r.status_code in [400, 422], \
            f"Expected 400/422, got {r.status_code}: {r.text}"
        print(f"\n✅ Negative amount rejected: {r.status_code}")

    @pytest.mark.sepa
    def test_create_transaction_past_due_date(
            self, api, base_url, new_consumer):
        """Past due date is rejected with 400."""
        consumer_id = new_consumer["id"]
        past_date = (
            datetime.now() - timedelta(days=30)
        ).strftime("%Y-%m-%d")

        r = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": fake.uuid4(),
                "idConsumer": consumer_id,
                "amount": 10.00,
                "dueDate": past_date,
                "collectionType": "DIRECT_DEBIT"
            }]
        )
        if r.status_code == 403:
            pytest.skip("No write permission for transactions")
        assert r.status_code in [400, 422], \
            f"Expected 400/422, got {r.status_code}: {r.text}"
        print(f"\n✅ Past due date rejected: {r.status_code}")

    @pytest.mark.sepa
    def test_create_transaction_missing_amount(
            self, api, base_url, new_consumer):
        """Missing amount is rejected with 400."""
        consumer_id = new_consumer["id"]
        due_date = (
            datetime.now() + timedelta(days=30)
        ).strftime("%Y-%m-%d")

        r = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": fake.uuid4(),
                "idConsumer": consumer_id,
                "dueDate": due_date,
                "collectionType": "DIRECT_DEBIT"
            }]
        )
        if r.status_code == 403:
            pytest.skip("No write permission for transactions")
        assert r.status_code in [400, 422], \
            f"Expected 400/422, got {r.status_code}: {r.text}"
        print(f"\n✅ Missing amount rejected: {r.status_code}")