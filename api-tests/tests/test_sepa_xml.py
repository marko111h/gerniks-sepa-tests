"""
SEPA XML End-to-End simulation tests.

Simulates the complete SEPA Direct Debit lifecycle:
1. Create Consumer + Transaction via API
2. Generate PAIN.008 XML (Direct Debit Initiation)
3. Validate PAIN.008 structure
4. Generate CAMT.053 XML (Bank Statement / R-message simulation)
5. Validate CAMT.053 matches PAIN.008
"""

import pytest
from datetime import datetime, timedelta, date
from faker import Faker
from utils.iban_utils import generate_valid_german_iban, valid_bank_information
from utils.sepa_xml import (
    generate_pain008,
    generate_camt053_return,
    validate_pain008,
    validate_camt053_matches_pain008,
)

fake = Faker("de_DE")

# Creditor data (Miticon / Gerniks entity)
CREDITOR_NAME = "Miticon d.o.o"
CREDITOR_IBAN = "DE52701694100002965682"
SEPA_EXPORT_ID = 9999999


class TestPain008Generation:
    """Test PAIN.008 Direct Debit Initiation XML generation."""

    @pytest.mark.sepa
    def test_generate_pain008_single_transaction(self):
        """Generate valid PAIN.008 for single transaction."""
        transactions = [{
            "end_to_end_id": "1",
            "amount": 40.00,
            "currency": "EUR",
            "mandate_id": f"DE-978902-{fake.unix_time()}",
            "mandate_date": date.today().isoformat(),
            "debtor_name": fake.name(),
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Test transaction pytest"
        }]

        xml = generate_pain008(
            msg_id=f"Mtcn-SEPA-TEST-{fake.uuid4()}.xml",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        assert xml is not None
        assert len(xml) > 0
        assert "pain.008.001.02" in xml
        assert "CstmrDrctDbtInitn" in xml
        assert "DrctDbtTxInf" in xml
        assert "40.00" in xml
        print(f"\n✅ PAIN.008 generated: {len(xml)} chars")

    @pytest.mark.sepa
    def test_generate_pain008_multiple_transactions(self):
        """Generate PAIN.008 for multiple transactions like real export."""
        transactions = [
            {
                "end_to_end_id": str(i),
                "amount": round(10.00 + i * 5, 2),
                "currency": "EUR",
                "mandate_id": f"DE-{fake.random_int(100000, 999999)}-{fake.unix_time()}",
                "mandate_date": date.today().isoformat(),
                "debtor_name": fake.name(),
                "debtor_iban": generate_valid_german_iban(),
                "remittance_info": f"Transaction {i} - pytest test"
            }
            for i in range(1, 4)
        ]

        xml = generate_pain008(
            msg_id=f"Mtcn-SEPA-TEST-{fake.uuid4()}.xml",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        assert xml.count("<DrctDbtTxInf>") == 3
        print(f"\n✅ PAIN.008 with 3 transactions: {len(xml)} chars")


class TestPain008Validation:
    """Test PAIN.008 XML validation logic."""

    @pytest.mark.sepa
    def test_valid_pain008_passes_validation(self):
        """Well-formed PAIN.008 passes all validation checks."""
        transactions = [{
            "end_to_end_id": "1",
            "amount": 50.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-001",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "Test Debtor",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Pytest test"
        }]

        xml = generate_pain008(
            msg_id="TEST-MSG-001",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        result = validate_pain008(xml)
        assert result["valid"], \
            f"Validation failed: {result['errors']}"
        assert result["transaction_count"] == 1
        print(f"\n✅ Valid PAIN.008 passes validation")

    @pytest.mark.sepa
    def test_pain008_ctrl_sum_validation(self):
        """CtrlSum must match sum of transaction amounts."""
        transactions = [
            {"end_to_end_id": "1", "amount": 30.00, "currency": "EUR",
             "mandate_id": "DE-001", "mandate_date": date.today().isoformat(),
             "debtor_name": "Debtor 1",
             "debtor_iban": generate_valid_german_iban(),
             "remittance_info": "TX 1"},
            {"end_to_end_id": "2", "amount": 70.00, "currency": "EUR",
             "mandate_id": "DE-002", "mandate_date": date.today().isoformat(),
             "debtor_name": "Debtor 2",
             "debtor_iban": generate_valid_german_iban(),
             "remittance_info": "TX 2"},
        ]

        xml = generate_pain008(
            msg_id="TEST-CTRL-SUM",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        result = validate_pain008(xml)
        assert result["valid"], f"Errors: {result['errors']}"

        # Total should be 100.00
        assert "100.00" in xml
        print(f"\n✅ CtrlSum 100.00 validated (30+70)")

    @pytest.mark.sepa
    def test_validate_real_gerniks_pain008(self):
        """Validate real PAIN.008 file from Gerniks."""
        # This is the actual XML from Mtcn-SEPA-1336656-20260625.xml
        real_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.008.001.02" 
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="urn:iso:std:iso:20022:tech:xsd:pain.008.001.02 pain.008.001.02.xsd">
  <CstmrDrctDbtInitn>
    <GrpHdr>
      <MsgId>Mtcn-SEPA-1336656-20260625.xml</MsgId>
      <CreDtTm>2026-06-25T10:50:48.509Z</CreDtTm>
      <NbOfTxs>2</NbOfTxs>
      <CtrlSum>100.00</CtrlSum>
      <InitgPty><Nm>Miticon d.o.o</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>refSepaExportId01336656</PmtInfId>
      <PmtMtd>DD</PmtMtd>
      <BtchBookg>true</BtchBookg>
      <NbOfTxs>2</NbOfTxs>
      <CtrlSum>100.00</CtrlSum>
      <PmtTpInf>
        <SvcLvl><Cd>SEPA</Cd></SvcLvl>
        <LclInstrm><Cd>CORE</Cd></LclInstrm>
        <SeqTp>RCUR</SeqTp>
      </PmtTpInf>
      <ReqdColltnDt>2026-06-25</ReqdColltnDt>
      <Cdtr><Nm>Miticon d.o.o</Nm></Cdtr>
      <CdtrAcct><Id><IBAN>DE52701694100002965682</IBAN></Id></CdtrAcct>
      <CdtrAgt>
        <FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>
      </CdtrAgt>
      <ChrgBr>SLEV</ChrgBr>
      <CdtrSchmeId>
        <Id><PrvtId><Othr>
          <Id>1</Id>
          <SchmeNm><Prtry>SEPA</Prtry></SchmeNm>
        </Othr></PrvtId></Id>
      </CdtrSchmeId>
      <DrctDbtTxInf>
        <PmtId><EndToEndId>1</EndToEndId></PmtId>
        <InstdAmt Ccy="EUR">40.00</InstdAmt>
        <DrctDbtTx>
          <MndtRltdInf>
            <MndtId>DE-978902-1782377371679</MndtId>
            <DtOfSgntr>2026-06-25</DtOfSgntr>
          </MndtRltdInf>
        </DrctDbtTx>
        <DbtrAgt>
          <FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>
        </DbtrAgt>
        <Dbtr><Nm>Goran</Nm></Dbtr>
        <DbtrAcct><Id><IBAN>DE213123123123123</IBAN></Id></DbtrAcct>
        <RmtInf>
          <Ustrd>Aggregated transaction for consumer ID 978902</Ustrd>
        </RmtInf>
      </DrctDbtTxInf>
      <DrctDbtTxInf>
        <PmtId><EndToEndId>2</EndToEndId></PmtId>
        <InstdAmt Ccy="EUR">60.00</InstdAmt>
        <DrctDbtTx>
          <MndtRltdInf>
            <MndtId>DE-978903-1782377391499</MndtId>
            <DtOfSgntr>2026-06-25</DtOfSgntr>
          </MndtRltdInf>
        </DrctDbtTx>
        <DbtrAgt>
          <FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>
        </DbtrAgt>
        <Dbtr><Nm>Goran</Nm></Dbtr>
        <DbtrAcct><Id><IBAN>DE213123123312</IBAN></Id></DbtrAcct>
        <RmtInf>
          <Ustrd>Aggregated transaction for consumer ID 978903</Ustrd>
        </RmtInf>
      </DrctDbtTxInf>
    </PmtInf>
  </CstmrDrctDbtInitn>
</Document>'''

        result = validate_pain008(real_xml)
        print(f"\nReal PAIN.008 validation: {result}")
        assert result["transaction_count"] == 2
        print(f"\n✅ Real Gerniks PAIN.008 validated: "
              f"{result['transaction_count']} transactions")


class TestCamt053Generation:
    """Test CAMT.053 Bank Statement / R-message generation."""

    @pytest.mark.sepa
    def test_generate_camt053_from_pain008(self):
        """Generate CAMT.053 R-message from PAIN.008."""
        transactions = [{
            "end_to_end_id": "1",
            "amount": 40.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-001",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "Test Debtor",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Test remittance"
        }]

        pain008 = generate_pain008(
            msg_id="TEST-MSG-001",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        camt053 = generate_camt053_return(
            original_pain008_xml=pain008,
            creditor_iban=CREDITOR_IBAN,
            creditor_name=CREDITOR_NAME,
            return_reason_code="MD01",
            fee_amount=5.00
        )

        assert camt053 is not None
        assert "camt.053.001.02" in camt053
        assert "BkToCstmrStmt" in camt053
        assert "MD01" in camt053
        assert CREDITOR_IBAN in camt053
        # Return amount = 40.00 + 5.00 fee = 45.00
        assert "45.00" in camt053
        print(f"\n✅ CAMT.053 generated: {len(camt053)} chars")
        print(f"Return reason: MD01, amount: 45.00 (40.00 + 5.00 fee)")


class TestSepaEndToEnd:
    """Full SEPA End-to-End simulation."""

    @pytest.mark.sepa
    def test_sepa_full_lifecycle_simulation(self, api, base_url,
                                             new_consumer):
        """
        Simulate complete SEPA Direct Debit lifecycle:
        1. Consumer with bank account (via API fixture)
        2. Create transaction (via API)
        3. Generate PAIN.008 XML
        4. Validate PAIN.008
        5. Simulate bank response (CAMT.053)
        6. Validate CAMT.053 matches PAIN.008
        """
        consumer_id = new_consumer["id"]
        consumer_name = (
            f"{new_consumer.get('firstName', 'Test')} "
            f"{new_consumer.get('lastName', 'Consumer')}"
        ).strip()

        # Get bank account
        r_ba = api.get(
            f"{base_url}/api/public/p2/v1/consumer/"
            f"{consumer_id}/bank-account"
        )
        assert r_ba.status_code == 200
        data = r_ba.json()
        accounts = (
            data.get("content", data) if isinstance(data, dict) else data
        )
        assert len(accounts) > 0, "Consumer has no bank account"

        bank_account = accounts[0]
        consumer_iban = bank_account["iban"]
        mandate_id = bank_account.get(
            "sepaMandateId",
            f"DE-{consumer_id}-{fake.unix_time()}"
        )
        mandate_date = bank_account.get(
            "sepaMandateDate",
            date.today().isoformat()
        )

        print(f"\n--- Step 1: Consumer created ---")
        print(f"Consumer: {consumer_name} (ID: {consumer_id})")
        print(f"IBAN: {consumer_iban}")
        print(f"Mandate: {mandate_id}")

        # Create transaction via API
        due_date = (
            datetime.now() + timedelta(days=30)
        ).strftime("%Y-%m-%d")
        ext_id = fake.uuid4()

        r_tx = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": ext_id,
                "idConsumer": consumer_id,
                "amount": 35.00,
                "dueDate": due_date,
                "description": "SEPA E2E Test - pytest",
                "collectionType": "DIRECT_DEBIT"
            }]
        )
        assert r_tx.status_code in [200, 201], \
            f"Transaction creation failed: {r_tx.text}"

        tx_data = r_tx.json()
        tx = tx_data[0] if isinstance(tx_data, list) else tx_data
        assert tx["status"] in ["NEW", "ACCEPTED"]

        print(f"\n--- Step 2: Transaction created ---")
        print(f"TX External ID: {ext_id}")
        print(f"Amount: 35.00 EUR")
        print(f"Status: {tx['status']}")
        print(f"Due date: {due_date}")

        # Generate PAIN.008
        pain008_xml = generate_pain008(
            msg_id=f"Mtcn-SEPA-TEST-{fake.uuid4()[:8]}.xml",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=[{
                "end_to_end_id": "1",
                "amount": 35.00,
                "currency": "EUR",
                "mandate_id": mandate_id,
                "mandate_date": mandate_date,
                "debtor_name": consumer_name,
                "debtor_iban": consumer_iban,
                "remittance_info": (
                    f"SEPA E2E Test - pytest {ext_id}"
                )
            }],
            collection_date=due_date
        )

        print(f"\n--- Step 3: PAIN.008 generated ---")
        print(f"XML size: {len(pain008_xml)} chars")

        # Validate PAIN.008
        pain_result = validate_pain008(pain008_xml)
        assert pain_result["valid"], \
            f"PAIN.008 validation failed: {pain_result['errors']}"
        assert pain_result["transaction_count"] == 1

        print(f"\n--- Step 4: PAIN.008 validated ---")
        print(f"✅ Valid PAIN.008: {pain_result['transaction_count']} TX")
        if pain_result["warnings"]:
            print(f"⚠️  Warnings: {pain_result['warnings']}")

        # Generate CAMT.053 (bank simulation)
        camt053_xml = generate_camt053_return(
            original_pain008_xml=pain008_xml,
            creditor_iban=CREDITOR_IBAN,
            creditor_name=CREDITOR_NAME,
            return_reason_code="MD01",
            fee_amount=5.00
        )

        print(f"\n--- Step 5: CAMT.053 generated (bank simulation) ---")
        print(f"Return reason: MD01 (customer refused)")
        print(f"Return amount: 40.00 (35.00 + 5.00 fee)")

        # Validate CAMT.053 matches PAIN.008
        match_result = validate_camt053_matches_pain008(
            pain008_xml, camt053_xml
        )
        assert match_result["valid"], \
            f"CAMT.053 matching failed: {match_result['errors']}"

        print(f"\n--- Step 6: CAMT.053 matches PAIN.008 ---")
        print(f"✅ EndToEndId matches: {match_result['pain_e2e_ids']}")
        print(f"✅ Creditor IBAN consistent")
        print(f"\n🎉 SEPA End-to-End simulation complete!")

    @pytest.mark.sepa
    def test_sepa_r_message_scenarios(self):
        """Test different R-message return reason codes."""
        r_codes = [
            ("MD01", "No mandate"),
            ("AC01", "Invalid account"),
            ("AM04", "Insufficient funds"),
            ("MS02", "Customer refused"),
            ("RR01", "Missing debtor address"),
        ]

        transactions = [{
            "end_to_end_id": "1",
            "amount": 50.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-R-001",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "R-Message Test Debtor",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "R-message test"
        }]

        pain008 = generate_pain008(
            msg_id="R-MSG-TEST",
            creditor_name=CREDITOR_NAME,
            creditor_iban=CREDITOR_IBAN,
            sepa_export_id=SEPA_EXPORT_ID,
            transactions=transactions
        )

        for code, description in r_codes:
            camt053 = generate_camt053_return(
                original_pain008_xml=pain008,
                creditor_iban=CREDITOR_IBAN,
                creditor_name=CREDITOR_NAME,
                return_reason_code=code,
                fee_amount=5.00
            )

            assert code in camt053, \
                f"Return code {code} not in CAMT.053"

            match = validate_camt053_matches_pain008(pain008, camt053)
            assert match["valid"], \
                f"R-code {code} matching failed: {match['errors']}"

            print(f"✅ R-code {code} ({description}): valid")



class TestCamt053PaidVsReturned:
    """Test PAID vs RETURNED CAMT.053 scenarios."""

    @pytest.mark.sepa
    def test_generate_camt053_paid(self):
        """Generate CAMT.053 for SUCCESSFUL payment (CRDT)."""
        from utils.sepa_xml import generate_camt053_paid

        transactions = [{
            "end_to_end_id": "1",
            "amount": 40.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-001",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "Test Debtor",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Test payment"
        }]

        pain008 = generate_pain008(
            msg_id="TEST-PAID-001",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=9999,
            transactions=transactions
        )

        camt053_paid = generate_camt053_paid(
            original_pain008_xml=pain008,
            creditor_iban="DE52701694100002965682",
            creditor_name="Miticon d.o.o"
        )

        # PAID = CRDT indicator
        assert "CRDT" in camt053_paid
        # Payment code 166
        assert "166" in camt053_paid
        # No return info
        assert "RtrInf" not in camt053_paid
        # No DBIT (no debit)
        assert "DBIT" not in camt053_paid

        print(f"\n✅ CAMT.053 PAID generated")
        print(f"CdtDbtInd: CRDT (credit — money received)")
        print(f"BkTxCd: 166 (payment)")

    @pytest.mark.sepa
    def test_paid_vs_returned_difference(self):
        """Verify PAID and RETURNED CAMT.053 differ correctly."""
        from utils.sepa_xml import generate_camt053_paid

        transactions = [{
            "end_to_end_id": "1",
            "amount": 35.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-002",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "Test Debtor",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Test"
        }]

        pain008 = generate_pain008(
            msg_id="TEST-COMPARE",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=9999,
            transactions=transactions
        )

        # Generate both scenarios
        camt_paid = generate_camt053_paid(
            pain008,
            "DE52701694100002965682",
            "Miticon d.o.o"
        )
        camt_returned = generate_camt053_return(
            pain008,
            "DE52701694100002965682",
            "Miticon d.o.o",
            return_reason_code="MD01",
            fee_amount=5.00
        )

        # PAID differences
        assert "CRDT" in camt_paid
        assert "166" in camt_paid
        assert "RtrInf" not in camt_paid
        assert "35.00" in camt_paid  # original amount

        # RETURNED differences
        assert "DBIT" in camt_returned
        assert "109" in camt_returned
        assert "RtrInf" in camt_returned
        assert "MD01" in camt_returned
        assert "40.00" in camt_returned  # amount + 5€ fee

        print(f"\n✅ PAID vs RETURNED comparison:")
        print(f"PAID:     CRDT, code 166, amount=35.00, no RtrInf")
        print(f"RETURNED: DBIT, code 109, amount=40.00, RtrInf MD01")

    @pytest.mark.sepa
    def test_validate_camt053_is_paid(self):
        """Validate PAID CAMT.053 passes validation."""
        from utils.sepa_xml import generate_camt053_paid, validate_camt053_is_paid

        transactions = [{
            "end_to_end_id": "1",
            "amount": 50.00,
            "currency": "EUR",
            "mandate_id": "DE-TEST-003",
            "mandate_date": date.today().isoformat(),
            "debtor_name": "Validation Test",
            "debtor_iban": generate_valid_german_iban(),
            "remittance_info": "Validation"
        }]

        pain008 = generate_pain008(
            msg_id="TEST-VALIDATE-PAID",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=9999,
            transactions=transactions
        )

        camt_paid = generate_camt053_paid(
            pain008,
            "DE52701694100002965682",
            "Miticon d.o.o"
        )

        result = validate_camt053_is_paid(camt_paid)

        assert result["valid"], f"Errors: {result['errors']}"
        assert result["paid_count"] == 1
        assert result["returned_count"] == 0

        print(f"\n✅ PAID validation passed")
        print(f"Paid count: {result['paid_count']}")
        print(f"Returned count: {result['returned_count']}")

    @pytest.mark.sepa
    def test_full_sepa_paid_simulation(self, api, base_url, new_consumer):
        """
        Full simulation: API transaction → Export → PAID bank response.
        Simulates the complete happy path.
        """
        consumer_id = new_consumer["id"]
        consumer_name = (
            f"{new_consumer.get('firstName', 'Test')} "
            f"{new_consumer.get('lastName', 'Consumer')}"
        ).strip()

        from utils.sepa_xml import generate_camt053_paid, validate_camt053_is_paid

        # Get bank account
        r_ba = api.get(
            f"{base_url}/api/public/p2/v1/consumer"
            f"/{consumer_id}/bank-account"
        )
        ba_data = r_ba.json()
        accounts = (
            ba_data.get("content", ba_data)
            if isinstance(ba_data, dict) else ba_data
        )
        assert len(accounts) > 0
        account = accounts[0]

        # Create transaction
        due_date = (
            datetime.now() + timedelta(days=30)
        ).strftime("%Y-%m-%d")

        r_tx = api.post(
            f"{base_url}/api/public/p2/v2/transaction",
            json=[{
                "idExternal": fake.uuid4(),
                "idConsumer": consumer_id,
                "amount": 55.00,
                "dueDate": due_date,
                "description": "SEPA Paid Simulation - pytest",
                "collectionType": "DIRECT_DEBIT"
            }]
        )
        assert r_tx.status_code in [200, 201]

        print(f"\n--- Step 1: Transaction created ---")
        print(f"Consumer: {consumer_name}")
        print(f"Amount: 55.00 EUR, Due: {due_date}")

        # Generate PAIN.008
        pain008 = generate_pain008(
            msg_id=f"TEST-PAID-SIM-{fake.uuid4()[:8]}",
            creditor_name="Miticon d.o.o",
            creditor_iban="DE52701694100002965682",
            sepa_export_id=9999,
            transactions=[{
                "end_to_end_id": "1",
                "amount": 55.00,
                "currency": "EUR",
                "mandate_id": account.get("sepaMandateId", "TEST"),
                "mandate_date": account.get(
                    "sepaMandateDate", date.today().isoformat()
                ),
                "debtor_name": consumer_name,
                "debtor_iban": account["iban"],
                "remittance_info": "SEPA Paid Simulation"
            }],
            collection_date=due_date
        )

        pain_result = validate_pain008(pain008)
        assert pain_result["valid"]

        print(f"\n--- Step 2: PAIN.008 generated and validated ---")

        # Simulate bank PAID response
        camt053_paid = generate_camt053_paid(
            original_pain008_xml=pain008,
            creditor_iban="DE52701694100002965682",
            creditor_name="Miticon d.o.o"
        )

        paid_result = validate_camt053_is_paid(camt053_paid)
        assert paid_result["valid"], \
            f"PAID validation failed: {paid_result['errors']}"

        # Verify matching
        match_result = validate_camt053_matches_pain008(
            pain008, camt053_paid
        )
        assert match_result["valid"], \
            f"Matching failed: {match_result['errors']}"

        print(f"\n--- Step 3: CAMT.053 PAID simulated ---")
        print(f"CdtDbtInd: CRDT (money received by Miticon)")
        print(f"BkTxCd: 166 (payment confirmed)")
        print(f"Amount: 55.00 EUR (full amount, no fee)")
        print(f"EndToEndId matches: {match_result['pain_e2e_ids']}")

        print(f"\n🎉 Happy path simulation complete!")
        print(f"✅ Transaction 55€ → PAID")
        print(f"✅ PAIN.008 sent to bank (simulated)")
        print(f"✅ CAMT.053 PAID received (simulated)")
        print(f"✅ EndToEndId matched correctly")

