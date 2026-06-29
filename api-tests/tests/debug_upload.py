import requests
import os
from dotenv import load_dotenv

load_dotenv()

bearer = os.getenv("BEARER_TOKEN")

# Upload uses ONLY Bearer token, no api-key!
headers = {
    "Authorization": f"Bearer {bearer}",
}

test_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt><GrpHdr><MsgId>TEST-123</MsgId></GrpHdr></BkToCstmrStmt>
</Document>'''

files = {
    "file": ("test_camt053.xml", test_xml, "text/xml")
}
data = {
    "aRelativePath": "E1/import-starmoney",
    "type": "EB_BANK_SEPA_STATEMENT_REPORT",
}

r = requests.post(
    "https://dev-cc.dev.gerniks.net/api/cmncommon/v4/cmnwebfile/upload",
    params={"delimiter": "undefined"},
    headers=headers,
    files=files,
    data=data
)

print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")