import requests
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

# Miticon parent entity headers for export
headers = {
    "Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}",
    "api-key": os.getenv("MITICON_API_KEY"),
    "Content-Type": "application/json"
}

collection_date = "2026-07-26T01:00:00.000Z"

r = requests.post(
    "https://dev-cc.dev.gerniks.net/api/ebbank/v3/ebsepaexport/exportsepaandget",
    headers=headers,
    json={
        "ebSepaExport": {
            "id": 0,
            "creationTypeCd": "MANUAL",
            "idMcBankAccount": 101,
            "idMcEntity": 1,
            "idSystemUser": 1,
            "idWebfile": 0,
            "requestedCollectionDate": collection_date,
            "sepaExportFilename": "",
            "statusCd": "EXPORTED",
            "statusDetails": "",
            "typeCd": "EBICS"
        },
        "groupByConsumerId": True,
        "transactionIds": [398242]
    }
)

print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Body length: {len(r.content)}")
print(f"Body: {r.text[:500]}")