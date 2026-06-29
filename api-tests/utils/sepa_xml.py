"""
SEPA XML Generator and Validator utilities.

Simulates PAIN.008 (Direct Debit Initiation) and 
CAMT.053 (Bank Statement with R-messages) without real bank.
"""

from datetime import datetime, date
from xml.etree import ElementTree as ET
import uuid


# Namespaces
PAIN008_NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"
CAMT053_NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"


def generate_pain008(
    msg_id: str,
    creditor_name: str,
    creditor_iban: str,
    sepa_export_id: int,
    transactions: list,
    collection_date: str = None
) -> str:
    if collection_date is None:
        collection_date = date.today().isoformat()

    total_amount = sum(tx["amount"] for tx in transactions)
    nb_of_txs = len(transactions)
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{PAIN008_NS}" 
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="{PAIN008_NS} pain.008.001.02.xsd">
  <CstmrDrctDbtInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{created_at}</CreDtTm>
      <NbOfTxs>{nb_of_txs}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <InitgPty><Nm>{creditor_name}</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>refSepaExportId0{sepa_export_id}</PmtInfId>
      <PmtMtd>DD</PmtMtd>
      <BtchBookg>true</BtchBookg>
      <NbOfTxs>{nb_of_txs}</NbOfTxs>
      <CtrlSum>{total_amount:.2f}</CtrlSum>
      <PmtTpInf>
        <SvcLvl><Cd>SEPA</Cd></SvcLvl>
        <LclInstrm><Cd>CORE</Cd></LclInstrm>
        <SeqTp>RCUR</SeqTp>
      </PmtTpInf>
      <ReqdColltnDt>{collection_date}</ReqdColltnDt>
      <Cdtr><Nm>{creditor_name}</Nm></Cdtr>
      <CdtrAcct><Id><IBAN>{creditor_iban}</IBAN></Id></CdtrAcct>
      <CdtrAgt>
        <FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>
      </CdtrAgt>
      <ChrgBr>SLEV</ChrgBr>
      <CdtrSchmeId>
        <Id><PrvtId><Othr>
          <Id>1</Id>
          <SchmeNm><Prtry>SEPA</Prtry></SchmeNm>
        </Othr></PrvtId></Id>
      </CdtrSchmeId>'''

    for tx in transactions:
        xml += f'''
      <DrctDbtTxInf>
        <PmtId><EndToEndId>{tx["end_to_end_id"]}</EndToEndId></PmtId>
        <InstdAmt Ccy="{tx.get("currency", "EUR")}">{tx["amount"]:.2f}</InstdAmt>
        <DrctDbtTx>
          <MndtRltdInf>
            <MndtId>{tx["mandate_id"]}</MndtId>
            <DtOfSgntr>{tx["mandate_date"]}</DtOfSgntr>
          </MndtRltdInf>
        </DrctDbtTx>
        <DbtrAgt>
          <FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>
        </DbtrAgt>
        <Dbtr><Nm>{tx["debtor_name"]}</Nm></Dbtr>
        <DbtrAcct><Id><IBAN>{tx["debtor_iban"]}</IBAN></Id></DbtrAcct>
        <RmtInf><Ustrd>{tx["remittance_info"]}</Ustrd></RmtInf>
      </DrctDbtTxInf>'''

    xml += '''
    </PmtInf>
  </CstmrDrctDbtInitn>
</Document>'''

    return xml


def generate_camt053_return(
    original_pain008_xml: str,
    creditor_iban: str,
    creditor_name: str,
    return_reason_code: str = "MD01",
    fee_amount: float = 5.00
) -> str:
    root = ET.fromstring(original_pain008_xml)
    ns = {"p": PAIN008_NS}

    transactions = root.findall(".//p:DrctDbtTxInf", ns)
    msg_id = f"{uuid.uuid4()}-{datetime.now().strftime('%Y%m%d')}"
    today = date.today().isoformat()
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    entries = []
    for tx in transactions:
        end_to_end_id = tx.find("p:PmtId/p:EndToEndId", ns).text
        amount = float(tx.find("p:InstdAmt", ns).text)
        mandate_id = tx.find("p:DrctDbtTx/p:MndtRltdInf/p:MndtId", ns).text
        debtor_name = tx.find("p:Dbtr/p:Nm", ns).text
        debtor_iban = tx.find("p:DbtrAcct/p:Id/p:IBAN", ns).text
        remittance = tx.find("p:RmtInf/p:Ustrd", ns).text or ""
        return_amount = amount + fee_amount

        entries.append({
            "end_to_end_id": end_to_end_id,
            "amount": return_amount,
            "original_amount": amount,
            "mandate_id": mandate_id,
            "debtor_name": debtor_name,
            "debtor_iban": debtor_iban,
            "remittance": remittance,
        })

    entries_xml = ""
    for entry in entries:
        entries_xml += f'''
      <Ntry>
        <Amt Ccy="EUR">{entry["amount"]:.2f}</Amt>
        <CdtDbtInd>DBIT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <BookgDt><Dt>{today}</Dt></BookgDt>
        <ValDt><Dt>{today}</Dt></ValDt>
        <AcctSvcrRef>{uuid.uuid4().hex[:20]}</AcctSvcrRef>
        <BkTxCd/>
        <NtryDtls>
          <TxDtls>
            <Refs>
              <EndToEndId>{entry["end_to_end_id"]}</EndToEndId>
              <MndtId>{entry["mandate_id"]}</MndtId>
            </Refs>
            <BkTxCd>
              <Prtry>
                <Cd>NRTI+109+00931+000</Cd>
              </Prtry>
            </BkTxCd>
            <RltdPties>
              <Dbtr><Nm>{entry["debtor_name"]}</Nm></Dbtr>
              <DbtrAcct><Id><IBAN>{entry["debtor_iban"]}</IBAN></Id></DbtrAcct>
              <Cdtr><Nm>{creditor_name}</Nm></Cdtr>
              <CdtrAcct><Id><IBAN>{creditor_iban}</IBAN></Id></CdtrAcct>
            </RltdPties>
            <RmtInf>
              <Ustrd>Retoure SEPA Lastschrift vom {today}, Rueckgabegrund: {return_reason_code}</Ustrd>
              <Ustrd>{entry["remittance"]}</Ustrd>
              <Ustrd>ORG.BETR.: {entry["original_amount"]:.2f} EUR IBAN: {entry["debtor_iban"]}</Ustrd>
            </RmtInf>
            <RtrInf>
              <Rsn><Cd>{return_reason_code}</Cd></Rsn>
            </RtrInf>
          </TxDtls>
        </NtryDtls>
      </Ntry>'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns="{CAMT053_NS}"
          xsi:schemaLocation="{CAMT053_NS} camt.053.001.02.xsd">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{created_at}</CreDtTm>
      <MsgPgntn>
        <PgNb>1</PgNb>
        <LastPgInd>true</LastPgInd>
      </MsgPgntn>
    </GrpHdr>
    <Stmt>
      <Id>{uuid.uuid4()}</Id>
      <ElctrncSeqNb>000000000</ElctrncSeqNb>
      <CreDtTm>{created_at}</CreDtTm>
      <Acct>
        <Id><IBAN>{creditor_iban}</IBAN></Id>
        <Ccy>EUR</Ccy>
      </Acct>
      <Bal>
        <Tp><CdOrPrtry><Cd>PRCD</Cd></CdOrPrtry></Tp>
        <Amt Ccy="EUR">14087.23</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt><Dt>{today}</Dt></Dt>
      </Bal>
      <Bal>
        <Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>
        <Amt Ccy="EUR">14034.23</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt><Dt>{today}</Dt></Dt>
      </Bal>{entries_xml}
    </Stmt>
  </BkToCstmrStmt>
</Document>'''


def generate_camt053_paid(
    original_pain008_xml: str,
    creditor_iban: str,
    creditor_name: str
) -> str:
    root = ET.fromstring(original_pain008_xml)
    ns = {"p": PAIN008_NS}

    transactions = root.findall(".//p:DrctDbtTxInf", ns)
    msg_id = f"{uuid.uuid4()}-{datetime.now().strftime('%Y%m%d')}"
    today = date.today().isoformat()
    created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    entries = []
    for tx in transactions:
        end_to_end_id = tx.find("p:PmtId/p:EndToEndId", ns).text
        amount = float(tx.find("p:InstdAmt", ns).text)
        debtor_name = tx.find("p:Dbtr/p:Nm", ns).text
        debtor_iban = tx.find("p:DbtrAcct/p:Id/p:IBAN", ns).text

        entries.append({
            "end_to_end_id": end_to_end_id,
            "amount": amount,
            "debtor_name": debtor_name,
            "debtor_iban": debtor_iban,
        })

    entries_xml = ""
    for entry in entries:
        entries_xml += f'''
      <Ntry>
        <Amt Ccy="EUR">{entry["amount"]:.2f}</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <BookgDt><Dt>{today}</Dt></BookgDt>
        <ValDt><Dt>{today}</Dt></ValDt>
        <AcctSvcrRef>{uuid.uuid4().hex[:20]}</AcctSvcrRef>
        <BkTxCd/>
        <NtryDtls>
          <TxDtls>
            <Refs>
              <EndToEndId>{entry["end_to_end_id"]}</EndToEndId>
            </Refs>
            <BkTxCd>
              <Prtry>
                <Cd>NRTI+166+9262+902</Cd>
              </Prtry>
            </BkTxCd>
            <RltdPties>
              <Dbtr><Nm>{entry["debtor_name"]}</Nm></Dbtr>
              <DbtrAcct><Id><IBAN>{entry["debtor_iban"]}</IBAN></Id></DbtrAcct>
              <Cdtr><Nm>{creditor_name}</Nm></Cdtr>
              <CdtrAcct><Id><IBAN>{creditor_iban}</IBAN></Id></CdtrAcct>
            </RltdPties>
          </TxDtls>
        </NtryDtls>
      </Ntry>'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns="{CAMT053_NS}"
          xsi:schemaLocation="{CAMT053_NS} camt.053.001.02.xsd">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{created_at}</CreDtTm>
      <MsgPgntn><PgNb>1</PgNb><LastPgInd>true</LastPgInd></MsgPgntn>
    </GrpHdr>
    <Stmt>
      <Id>{uuid.uuid4()}</Id>
      <ElctrncSeqNb>000000000</ElctrncSeqNb>
      <CreDtTm>{created_at}</CreDtTm>
      <Acct>
        <Id><IBAN>{creditor_iban}</IBAN></Id>
        <Ccy>EUR</Ccy>
      </Acct>
      <Bal>
        <Tp><CdOrPrtry><Cd>PRCD</Cd></CdOrPrtry></Tp>
        <Amt Ccy="EUR">14087.23</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt><Dt>{today}</Dt></Dt>
      </Bal>
      <Bal>
        <Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp>
        <Amt Ccy="EUR">14034.23</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Dt><Dt>{today}</Dt></Dt>
      </Bal>{entries_xml}
    </Stmt>
  </BkToCstmrStmt>
</Document>'''


def validate_pain008(xml_str: str) -> dict:
    errors = []
    warnings = []

    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        return {"valid": False, "errors": [f"XML parse error: {e}"]}

    ns = {"p": PAIN008_NS}

    checks = [
        (".//p:GrpHdr/p:MsgId", "MsgId"),
        (".//p:GrpHdr/p:CreDtTm", "CreDtTm"),
        (".//p:GrpHdr/p:NbOfTxs", "NbOfTxs"),
        (".//p:GrpHdr/p:CtrlSum", "CtrlSum"),
        (".//p:PmtInf/p:ReqdColltnDt", "ReqdColltnDt"),
        (".//p:Cdtr/p:Nm", "Creditor Name"),
        (".//p:CdtrAcct/p:Id/p:IBAN", "Creditor IBAN"),
    ]

    for xpath, name in checks:
        el = root.find(xpath, ns)
        if el is None or not el.text:
            errors.append(f"Missing required field: {name}")

    nb_of_txs_el = root.find(".//p:GrpHdr/p:NbOfTxs", ns)
    txs = root.findall(".//p:DrctDbtTxInf", ns)
    if nb_of_txs_el is not None:
        declared = int(nb_of_txs_el.text)
        actual = len(txs)
        if declared != actual:
            errors.append(
                f"NbOfTxs mismatch: declared {declared}, actual {actual}"
            )

    ctrl_sum_el = root.find(".//p:GrpHdr/p:CtrlSum", ns)
    if ctrl_sum_el is not None:
        declared_sum = float(ctrl_sum_el.text)
        actual_sum = sum(
            float(tx.find("p:InstdAmt", ns).text)
            for tx in txs
            if tx.find("p:InstdAmt", ns) is not None
        )
        if abs(declared_sum - actual_sum) > 0.01:
            errors.append(
                f"CtrlSum mismatch: declared {declared_sum}, "
                f"actual {actual_sum:.2f}"
            )

    for i, tx in enumerate(txs):
        end_to_end = tx.find("p:PmtId/p:EndToEndId", ns)
        if end_to_end is None or not end_to_end.text:
            errors.append(f"TX {i+1}: Missing EndToEndId")

        iban = tx.find("p:DbtrAcct/p:Id/p:IBAN", ns)
        if iban is not None and iban.text:
            if not iban.text.startswith("DE") and len(iban.text) < 15:
                warnings.append(f"TX {i+1}: IBAN looks invalid: {iban.text}")

        amount = tx.find("p:InstdAmt", ns)
        if amount is not None:
            try:
                val = float(amount.text)
                if val <= 0:
                    errors.append(
                        f"TX {i+1}: Amount must be positive, got {val}"
                    )
            except ValueError:
                errors.append(f"TX {i+1}: Invalid amount: {amount.text}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "transaction_count": len(txs),
    }


def validate_camt053_matches_pain008(
        pain008_xml: str, camt053_xml: str) -> dict:
    errors = []

    p_ns = {"p": PAIN008_NS}
    c_ns = {"c": CAMT053_NS}

    try:
        pain_root = ET.fromstring(pain008_xml)
        camt_root = ET.fromstring(camt053_xml)
    except ET.ParseError as e:
        return {"valid": False, "errors": [f"XML parse error: {e}"]}

    pain_e2e_ids = {
        el.text for el in pain_root.findall(".//p:EndToEndId", p_ns)
    }
    camt_e2e_ids = {
        el.text for el in camt_root.findall(".//c:EndToEndId", c_ns)
    }

    missing = pain_e2e_ids - camt_e2e_ids
    if missing:
        errors.append(
            f"CAMT.053 missing EndToEndId(s) from PAIN.008: {missing}"
        )

    unknown = camt_e2e_ids - pain_e2e_ids
    if unknown:
        errors.append(
            f"CAMT.053 contains unknown EndToEndId(s): {unknown}"
        )

    pain_creditor_iban = pain_root.find(".//p:CdtrAcct/p:Id/p:IBAN", p_ns)
    camt_creditor_iban = camt_root.find(".//c:Acct/c:Id/c:IBAN", c_ns)

    if pain_creditor_iban is not None and camt_creditor_iban is not None:
        if pain_creditor_iban.text != camt_creditor_iban.text:
            errors.append(
                f"Creditor IBAN mismatch: "
                f"PAIN={pain_creditor_iban.text}, "
                f"CAMT={camt_creditor_iban.text}"
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "pain_e2e_ids": list(pain_e2e_ids),
        "camt_e2e_ids": list(camt_e2e_ids),
    }


def validate_camt053_is_paid(camt053_xml: str) -> dict:
    errors = []
    warnings = []

    try:
        root = ET.fromstring(camt053_xml)
    except ET.ParseError as e:
        return {"valid": False, "errors": [f"XML parse error: {e}"]}

    ns = {"c": CAMT053_NS}

    entries = root.findall(".//c:Ntry", ns)
    if not entries:
        errors.append("No entries found in CAMT.053")
        return {"valid": False, "errors": errors}

    paid_count = 0
    returned_count = 0

    for entry in entries:
        cdt_dbt = entry.find("c:CdtDbtInd", ns)
        if cdt_dbt is not None:
            if cdt_dbt.text == "CRDT":
                paid_count += 1
            elif cdt_dbt.text == "DBIT":
                returned_count += 1

        bank_code = entry.find(".//c:BkTxCd/c:Prtry/c:Cd", ns)
        if bank_code is not None:
            if "109" in bank_code.text:
                warnings.append(
                    "Found return code 109 — this is a return, not payment"
                )

        rtr_inf = entry.find(".//c:RtrInf", ns)
        if rtr_inf is not None:
            errors.append(
                "Found RtrInf in PAID statement — "
                "this indicates a return, not payment"
            )

    if paid_count == 0:
        errors.append("No CRDT entries found — no payments detected")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "paid_count": paid_count,
        "returned_count": returned_count
    }


def upload_camt053_and_import(
    camt053_xml: str,
    bearer_token: str,
    miticon_api_key: str = None,
    base_url: str = "https://dev-cc.dev.gerniks.net/api"
) -> dict:
    """
    Upload CAMT.053 XML to CashControl and trigger import.
    Upload uses only Bearer token (no api-key).
    """
    import requests as req

    upload_headers = {
        "Authorization": f"Bearer {bearer_token}",
    }

    files = {
        "file": (
            f"camt053_{uuid.uuid4().hex[:8]}.xml",
            camt053_xml.encode("utf-8"),
            "text/xml"
        )
    }
    data = {
        "aRelativePath": "E1/import-starmoney",
        "type": "EB_BANK_SEPA_STATEMENT_REPORT",
    }

    r_upload = req.post(
        f"{base_url}/cmncommon/v4/cmnwebfile/upload",
        params={"delimiter": "undefined"},
        headers=upload_headers,
        files=files,
        data=data
    )

    if r_upload.status_code != 200:
        return {
            "success": False,
            "step": "upload",
            "status": r_upload.status_code,
            "error": r_upload.text[:300]
        }

    upload_data = r_upload.json()
    webfile_id = upload_data["id"]

    import_headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    r_import = req.post(
        f"{base_url}/ebbank/v3/ebsepastatementreport/importfile/{webfile_id}",
        headers=import_headers,
        json={}
    )

    return {
        "success": r_import.status_code in [200, 201],
        "step": "import",
        "webfile_id": webfile_id,
        "upload_data": upload_data,
        "import_status": r_import.status_code,
        "import_response": r_import.text[:500]
    }