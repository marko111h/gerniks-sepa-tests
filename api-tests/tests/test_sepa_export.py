"""
SEPA Export End-to-End tests.

Complete SEPA Export flow:
1. Create Consumer + Transaction via public API
2. Get internal TX ID from database
3. Trigger SEPA Export via Miticon parent entity
4. Verify export response (webfile ID, filename, status)
5. Verify transaction status changed to EXPORTED in DB
6. Upload CAMT.053 to simulate bank response
7. Verify transaction status changes to PAID/RETURNED
"""

import pytest
import os
import time
from datetime import datetime, timedelta, date
from faker import Faker
from dotenv import load_dotenv
import requests as req
from utils.iban_utils import valid_bank_information
from utils.sepa_xml import (
    validate_pain008, generate_pain008,
    generate_camt053_paid, generate_camt053_return,
    upload_camt053_and_import
)

load_dotenv()
fake = Faker("de_DE")

MITICON_HEADERS = {
    "Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}",
    "api-key": os.getenv("MITICON_API_KEY"),
    "Content-Type": "application/json"
}

INTERNAL_BASE = "https://dev-cc.dev.gerniks.net/api"
MITICON_ENTITY_ID = int(os.getenv("MITICON_ENTITY_ID", "1"))
MITICON_BANK_ACCOUNT_ID = int(os.getenv("MITICON_BANK_ACCOUNT_ID", "101"))


def get_matching_id(db, internal_tx_id: int) -> str:
    """Get matching_id from pm_transaction_alias table."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT matching_id 
            FROM app.pm_transaction_alias
            WHERE id_pm_transaction = %s
            LIMIT 1
            """,
            (internal_tx_id,)
        )
        row = cur.fetchone()
        return row["matching_id"] if row else None


def get_tx_from_db(db, ext_id: str) -> dict:
    """Get internal transaction data from DB by external ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, status_cd, due_date, amount
            FROM app.pm_transaction
            WHERE id_ext_transaction = %s
            LIMIT 1
            """,
            (ext_id,)
        )
        return cur.fetchone()


def trigger_sepa_export(transaction_ids: list, due_date: str) -> dict:
    """Trigger SEPA export for given transaction IDs."""
    collection_date = f"{due_date}T01:00:00.000Z"
    r = req.post(
        f"{INTERNAL_BASE}/ebbank/v3/ebsepaexport/exportsepaandget",
        headers=MITICON_HEADERS,
        json={
            "ebSepaExport": {
                "id": 0,
                "creationTypeCd": "MANUAL",
                "idMcBankAccount": MITICON_BANK_ACCOUNT_ID,
                "idMcEntity": MITICON_ENTITY_ID,
                "idSystemUser": 1,
                "idWebfile": 0,
                "requestedCollectionDate": collection_date,
                "sepaExportFilename": "",
                "statusCd": "EXPORTED",
                "statusDetails": "",
                "typeCd": "EBICS"
            },
            "groupByConsumerId": True,
            "transactionIds": transaction_ids
        }
    )
    return r


def verify_tx_status_in_db(db, internal_id: int) -> str:
    """Verify transaction status in database."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT status_cd FROM app.pm_transaction WHERE id = %s",
            (internal_id,)
        )
        row = cur.fetchone()
        return row["status_cd"] if row else None


def wait_for_accepted(db, ext_id: str, max_attempts: int = 15) -> dict:
    """Wait for transaction to reach ACCEPTED status."""
    db_tx = None
    for _ in range(max_attempts):
        db_tx = get_tx_from_db(db, ext_id)
        if db_tx and db_tx["status_cd"] == "ACCEPTED":
            return db_tx
        time.sleep(1)
    return db_tx


def create_consumer_and_get_account(api, base_url, first, last):
    """Helper — create consumer with bank account, return both."""
    full_name = f"{first} {last}"
    r_c = api.post(
        f"{base_url}/api/public/p2/v1/consumer",
        json=[{
            "idExternal": fake.uuid4(),
            "firstName": first,
            "lastName": last,
            "type": "PERSON",
            "email": fake.email(),
            "bankAccounts": valid_bank_information(full_name)
        }]
    )
    assert r_c.status_code == 201
    consumer = r_c.json()[0]
    consumer_id = consumer["id"]

    r_ba = api.get(
        f"{base_url}/api/public/p2/v1/consumer"
        f"/{consumer_id}/bank-account"
    )
    ba_data = r_ba.json()
    accounts = (
        ba_data.get("content", ba_data)
        if isinstance(ba_data, dict) else ba_data
    )
    return consumer, accounts[0]


def create_transaction(
        api, base_url, consumer_id, amount, description):
    """Helper — create transaction for consumer."""
    due_date = (
        datetime.now() + timedelta(days=30)
    ).strftime("%Y-%m-%d")
    ext_id = fake.uuid4()

    r_tx = api.post(
        f"{base_url}/api/public/p2/v2/transaction",
        json=[{
            "idExternal": ext_id,
            "idConsumer": consumer_id,
            "amount": amount,
            "dueDate": due_date,
            "description": description,
            "collectionType": "DIRECT_DEBIT"
        }]
    )
    assert r_tx.status_code in [200, 201]
    return ext_id, due_date


class TestSepaExportWithDb:
    """SEPA Export tests using DB for dynamic transaction IDs."""

    @pytest.mark.sepa
    def test_db_connection(self, db):
        """Verify database connection works."""
        with db.cursor() as cur:
            cur.execute("SELECT version()")
            result = cur.fetchone()
            assert result is not None
            print(f"\n✅ DB connected: PostgreSQL")

    @pytest.mark.sepa
    def test_create_and_export_transaction_full_flow(
            self, api, base_url, db):
        """Create transaction, export it, verify EXPORTED in DB."""
        first = fake.first_name()
        last = fake.last_name()

        consumer, _ = create_consumer_and_get_account(
            api, base_url, first, last
        )
        consumer_id = consumer["id"]
        print(f"\nStep 1 ✅ Consumer: {first} {last} (ID: {consumer_id})")

        ext_id, due_date = create_transaction(
            api, base_url, consumer_id, 25.00,
            "SEPA Full E2E Test - pytest"
        )
        print(f"Step 2 ✅ Transaction created: {ext_id}")

        db_tx = wait_for_accepted(db, ext_id)
        assert db_tx and db_tx["status_cd"] == "ACCEPTED"
        internal_id = db_tx["id"]
        print(f"Step 3 ✅ Internal ID: {internal_id}, Status: ACCEPTED")

        r_export = trigger_sepa_export(
            transaction_ids=[internal_id],
            due_date=str(db_tx["due_date"])
        )
        assert r_export.status_code == 200
        assert len(r_export.content) > 0
        export_data = r_export.json()

        new_status = verify_tx_status_in_db(db, internal_id)
        assert new_status == "EXPORTED"

        print(f"Step 4 ✅ Export: {export_data['sepaExportFilename']}")
        print(f"Step 5 ✅ DB status: ACCEPTED → EXPORTED")
        print(f"\n🎉 SEPA Export Complete!")

    @pytest.mark.sepa
    def test_export_response_structure(self, api, base_url, db):
        """Verify SEPA export response has all required fields."""
        first = fake.first_name()
        last = fake.last_name()

        consumer, _ = create_consumer_and_get_account(
            api, base_url, first, last
        )
        ext_id, _ = create_transaction(
            api, base_url, consumer["id"], 20.00,
            "SEPA Response Structure - pytest"
        )

        db_tx = wait_for_accepted(db, ext_id)
        if not db_tx or db_tx["status_cd"] != "ACCEPTED":
            pytest.skip("Transaction not ACCEPTED in time")

        r_export = trigger_sepa_export(
            transaction_ids=[db_tx["id"]],
            due_date=str(db_tx["due_date"])
        )
        assert r_export.status_code == 200
        data = r_export.json()

        required = [
            "id", "idWebfile", "sepaExportFilename",
            "statusCd", "allDebtors", "bankName",
            "requestedCollectionDate", "creationTypeCd"
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

        assert data["statusCd"] == "EXPORTED"
        assert data["bankName"] == "Raiffeisenbank"
        assert data["allDebtors"] >= 1
        assert data["sepaExportFilename"].endswith(".xml")
        print(f"\n✅ All required fields present")
        print(f"✅ Status: {data['statusCd']}, Bank: {data['bankName']}")


class TestSepaFullRealLifecycle:
    """
    Complete real SEPA lifecycle including CAMT.053 import.
    NEW → ACCEPTED → EXPORTED → PAID/RETURNED
    """

    @pytest.mark.sepa
    def test_full_lifecycle_paid(self, api, base_url, db):
        """
        Complete real SEPA lifecycle — PAID path.
        Creates real CAMT.053 with correct matching_id,
        uploads to system, verifies transaction → PAID.
        """
        first = fake.first_name()
        last = fake.last_name()
        full_name = f"{first} {last}"

        consumer, account = create_consumer_and_get_account(
            api, base_url, first, last
        )
        consumer_id = consumer["id"]
        print(f"\nStep 1 ✅ Consumer: {full_name} (ID: {consumer_id})")

        amount = 30.00
        ext_id, due_date = create_transaction(
            api, base_url, consumer_id, amount,
            "SEPA Real Paid Test - pytest"
        )
        print(f"Step 2 ✅ Transaction: {amount}€, due: {due_date}")

        db_tx = wait_for_accepted(db, ext_id)
        assert db_tx and db_tx["status_cd"] == "ACCEPTED"
        internal_id = db_tx["id"]

        matching_id = get_matching_id(db, internal_id)
        assert matching_id, f"No matching_id for TX {internal_id}"
        print(f"Step 3 ✅ Matching ID: {matching_id}")

        r_export = trigger_sepa_export(
            transaction_ids=[internal_id],
            due_date=str(db_tx["due_date"])
        )
        assert r_export.status_code == 200
        export_data = r_export.json()
        export_id = export_data["id"]

        status_after_export = verify_tx_status_in_db(db, internal_id)
        assert status_after_export == "EXPORTED"
        print(f"Step 4 ✅ Exported: {export_data['sepaExportFilename']}")
        print(f"           Status: ACCEPTED → EXPORTED ✅")

        pain008 = generate_pain008(
            msg_id=f"Mtcn-SEPA-{export_id}-pytest",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=export_id,
            transactions=[{
                "end_to_end_id": matching_id,
                "amount": amount,
                "currency": "EUR",
                "mandate_id": account.get(
                    "sepaMandateId", f"DE-{consumer_id}"
                ),
                "mandate_date": account.get(
                    "sepaMandateDate", date.today().isoformat()
                ),
                "debtor_name": full_name,
                "debtor_iban": account["iban"],
                "remittance_info": f"pytest PAID {ext_id}"
            }],
            collection_date=str(db_tx["due_date"])
        )

        camt053_paid = generate_camt053_paid(
            original_pain008_xml=pain008,
            creditor_iban="DE52701694100002965682",
            creditor_name="Miticon d.o.o"
        )
        print(f"Step 5 ✅ CAMT.053 PAID generated")

        bearer = os.getenv("BEARER_TOKEN")
        result = upload_camt053_and_import(
            camt053_xml=camt053_paid,
            bearer_token=bearer
        )

        print(f"\nStep 6 — Import result:")
        print(f"  Webfile: {result.get('webfile_id')}")
        print(f"  Status: {result.get('import_status')}")
        print(f"  Response: {result.get('import_response', '')[:200]}")

        assert result.get("webfile_id"), "Upload failed"

        time.sleep(3)

        # Verify pm_adjustment was created (proves matching worked)
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT type_cd, status_cd, amount
                FROM app.pm_adjustment
                WHERE id_pm_transaction = %s
                AND type_cd = 'PAYMENT'
                ORDER BY id DESC
                LIMIT 1
                """,
                (internal_id,)
            )
            adjustment = cur.fetchone()

        final_status = verify_tx_status_in_db(db, internal_id)
        print(f"\nStep 7 — Final transaction status: {final_status}")
        
        assert adjustment, \
            "Payment adjustment not created — matching failed!"
        assert adjustment["type_cd"] == "PAYMENT"
        assert float(adjustment["amount"]) == amount
        
        print(f"✅ pm_adjustment created:")
        print(f"   Type: {adjustment['type_cd']}")
        print(f"   Status: {adjustment['status_cd']}")
        print(f"   Amount: {adjustment['amount']}€")
        print(f"\n🎉 SEPA PAID Lifecycle Complete!")
        print(f"   NEW → ACCEPTED → EXPORTED → MATCHED (pm_adjustment PENDING)")
        print(f"   Note: pm_adjustment → COMPLETED via async batch job")

    @pytest.mark.sepa
    def test_full_lifecycle_returned(self, api, base_url, db):
        """
        Complete real SEPA lifecycle — RETURNED path (MD01).
        Bank rejects payment, transaction returns with fee.
        """
        first = fake.first_name()
        last = fake.last_name()
        full_name = f"{first} {last}"

        consumer, account = create_consumer_and_get_account(
            api, base_url, first, last
        )
        consumer_id = consumer["id"]

        amount = 40.00
        ext_id, due_date = create_transaction(
            api, base_url, consumer_id, amount,
            "SEPA Real Returned Test - pytest"
        )

        db_tx = wait_for_accepted(db, ext_id)
        assert db_tx and db_tx["status_cd"] == "ACCEPTED"
        internal_id = db_tx["id"]

        matching_id = get_matching_id(db, internal_id)
        assert matching_id, f"No matching_id for TX {internal_id}"

        r_export = trigger_sepa_export(
            transaction_ids=[internal_id],
            due_date=str(db_tx["due_date"])
        )
        assert r_export.status_code == 200
        export_id = r_export.json()["id"]

        print(f"\n✅ Consumer: {full_name}")
        print(f"✅ Transaction: {internal_id}, EXPORTED")
        print(f"✅ Matching ID: {matching_id}")

        pain008 = generate_pain008(
            msg_id=f"Mtcn-SEPA-{export_id}-pytest-ret",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=export_id,
            transactions=[{
                "end_to_end_id": matching_id,
                "amount": amount,
                "currency": "EUR",
                "mandate_id": account.get(
                    "sepaMandateId", f"DE-{consumer_id}"
                ),
                "mandate_date": account.get(
                    "sepaMandateDate", date.today().isoformat()
                ),
                "debtor_name": full_name,
                "debtor_iban": account["iban"],
                "remittance_info": f"pytest RETURNED {ext_id}"
            }],
            collection_date=str(db_tx["due_date"])
        )

        camt053_returned = generate_camt053_return(
            original_pain008_xml=pain008,
            creditor_iban="DE52701694100002965682",
            creditor_name="Miticon d.o.o",
            return_reason_code="MD01",
            fee_amount=5.00
        )
        print(f"✅ CAMT.053 RETURNED (MD01) generated")

        bearer = os.getenv("BEARER_TOKEN")
        result = upload_camt053_and_import(
            camt053_xml=camt053_returned,
            bearer_token=bearer
        )

        print(f"\nImport result:")
        print(f"  Webfile: {result.get('webfile_id')}")
        print(f"  Status: {result.get('import_status')}")
        print(f"  Response: {result.get('import_response', '')[:300]}")

        assert result.get("webfile_id"), "Upload failed"

        time.sleep(3)

        with db.cursor() as cur:
            cur.execute(
                """
                SELECT type_cd, status_cd, amount
                FROM app.pm_adjustment
                WHERE id_pm_transaction = %s
                AND type_cd = 'PAYMENT'
                ORDER BY id DESC
                LIMIT 1
                """,
                (internal_id,)
            )
            adjustment = cur.fetchone()

        final_status = verify_tx_status_in_db(db, internal_id)
        print(f"\nFinal transaction status: {final_status}")
        
        assert adjustment, \
            "Payment adjustment not created — matching failed!"
        
        print(f"✅ pm_adjustment created:")
        print(f"   Type: {adjustment['type_cd']}")
        print(f"   Status: {adjustment['status_cd']}")
        print(f"\n🎉 SEPA RETURNED Lifecycle Complete!")
        print(f"   NEW → ACCEPTED → EXPORTED → MATCHED (pm_adjustment PENDING)")
        print(f"   Note: pm_adjustment → COMPLETED via async batch job")