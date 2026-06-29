import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from utils.sepa_xml import (
    generate_pain008, generate_camt053_paid,
    generate_camt053_return, upload_camt053_and_import
)
from utils.iban_utils import generate_valid_german_iban
from datetime import date, datetime, timedelta

# Generate test PAIN.008
pain008 = generate_pain008(
    msg_id="DEBUG-TEST-001",
    creditor_name="Miticon d.o.o",
    creditor_iban="DE52701694100002965682",
    sepa_export_id=9999,
    transactions=[{
        "end_to_end_id": "1",
        "amount": 30.00,
        "currency": "EUR",
        "mandate_id": "DE-TEST-DEBUG-001",
        "mandate_date": date.today().isoformat(),
        "debtor_name": "Debug Test Debtor",
        "debtor_iban": generate_valid_german_iban(),
        "remittance_info": "Debug test"
    }],
    collection_date=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
)

# Generate PAID
camt_paid = generate_camt053_paid(
    original_pain008_xml=pain008,
    creditor_iban="DE52701694100002965682",
    creditor_name="Miticon d.o.o"
)

print("=== CAMT.053 PAID XML ===")
print(camt_paid)

print("\n\n=== Uploading PAID ===")
result = upload_camt053_and_import(
    camt053_xml=camt_paid,
    bearer_token=os.getenv("BEARER_TOKEN")
)
print(f"Upload webfile_id: {result.get('webfile_id')}")
print(f"Import status: {result.get('import_status')}")
print(f"Import response: {result.get('import_response')}")

# Generate RETURNED
camt_returned = generate_camt053_return(
    original_pain008_xml=pain008,
    creditor_iban="DE52701694100002965682",
    creditor_name="Miticon d.o.o",
    return_reason_code="MD01",
    fee_amount=5.00
)

print("\n\n=== CAMT.053 RETURNED XML ===")
print(camt_returned)

print("\n\n=== Uploading RETURNED ===")
result2 = upload_camt053_and_import(
    camt053_xml=camt_returned,
    bearer_token=os.getenv("BEARER_TOKEN")
)
print(f"Upload webfile_id: {result2.get('webfile_id')}")
print(f"Import status: {result2.get('import_status')}")
print(f"Import response: {result2.get('import_response')}")