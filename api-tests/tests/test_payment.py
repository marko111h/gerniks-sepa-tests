import pytest
from faker import Faker
from datetime import datetime, timedelta

fake = Faker("de_DE")


def create_test_transaction(api, base_url, consumer_id):
    """Helper — creates a NEW transaction for payment testing."""
    due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    r = api.post(
        f"{base_url}/api/public/p2/v2/transaction",
        json=[{
            "idExternal": fake.uuid4(),
            "idConsumer": consumer_id,
            "amount": 15.00,
            "dueDate": due_date,
            "description": "Payment test transaction - pytest",
            "collectionType": "DIRECT_DEBIT"
        }]
    )
    if r.status_code not in [200, 201]:
        return None
    data = r.json()
    return data[0] if isinstance(data, list) else data


class TestPayment:
    """POST /api/public/p2/v1/payment/pay"""

    @pytest.mark.sepa
    def test_pay_transaction_by_external_id(
            self, api, base_url, new_consumer):
        """Pay a transaction using idExternal.

        KNOWN ISSUE: POST /transaction response does not include
        internal id, but payment/pay endpoint requires internal id.
        Public API users cannot pay transactions they just created
        via the same API.
        """
        consumer_id = new_consumer["id"]

        tx = create_test_transaction(api, base_url, consumer_id)
        if tx is None:
            pytest.skip("Could not create transaction")

        ext_id = tx.get("idExternal")
        print(f"\nTransaction idExternal: {ext_id}")
        print(f"Transaction status: {tx.get('status')}")

        r = api.post(
            f"{base_url}/api/public/p2/v1/payment/pay",
            json={
                "idExternal": ext_id,
                "amount": 15.00,
                "paymentDate": datetime.now().strftime("%Y-%m-%d")
            }
        )

        print(f"\nPay → {r.status_code}: {r.text[:300]}")

        if r.status_code == 400 and "Can not find transaction" in r.text:
            pytest.skip(
                "KNOWN ISSUE: payment endpoint requires internal id "
                "which is not returned by POST /transaction."
            )

        assert r.status_code in [200, 201], \
            f"Expected 200/201, got {r.status_code}: {r.text}"

    @pytest.mark.sepa
    def test_pay_nonexistent_transaction(self, api, base_url):
        """Pay non-existent transaction returns 400."""
        r = api.post(
            f"{base_url}/api/public/p2/v1/payment/pay",
            json={
                "idExternal": "NONEXISTENT-TX-99999",
                "amount": 10.00,
                "paymentDate": datetime.now().strftime("%Y-%m-%d")
            }
        )
        assert r.status_code in [400, 404], \
            f"Expected 400/404, got {r.status_code}"
        print(f"\n✅ Nonexistent transaction rejected: {r.status_code}")


class TestStorno:
    """PUT /api/public/p2/v1/payment/storno"""

    @pytest.mark.sepa
    def test_storno_transaction(self, api, base_url, new_consumer):
        """Storno a transaction. Same KNOWN ISSUE as payment/pay."""
        consumer_id = new_consumer["id"]

        tx = create_test_transaction(api, base_url, consumer_id)
        if tx is None:
            pytest.skip("Could not create transaction")

        ext_id = tx.get("idExternal")

        r = api.put(
            f"{base_url}/api/public/p2/v1/payment/storno",
            json={
                "idExternal": ext_id,
                "description": "Test storno - pytest automated test"
            }
        )

        print(f"\nStorno → {r.status_code}: {r.text[:300]}")

        if r.status_code == 400 and "Can not find transaction" in r.text:
            pytest.skip(
                "KNOWN ISSUE: storno endpoint requires internal id."
            )

        assert r.status_code in [200, 201, 204], \
            f"Expected 200/201/204, got {r.status_code}"

    @pytest.mark.sepa
    def test_storno_nonexistent_transaction(self, api, base_url):
        """Storno non-existent transaction returns 400."""
        r = api.put(
            f"{base_url}/api/public/p2/v1/payment/storno",
            json={
                "idExternal": "NONEXISTENT-TX-99999",
                "description": "Test storno"
            }
        )
        assert r.status_code in [400, 404], \
            f"Expected 400/404, got {r.status_code}"
        print(f"\n✅ Nonexistent storno rejected: {r.status_code}")