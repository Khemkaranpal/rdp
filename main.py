import json
import os
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, status

app = FastAPI(
    title="India Financial & Banking Rails API",
    description="Ultra-fast validation for Indian Banking, GST, PAN, and IFSC rails",
    version="1.0.0"
)

# Server start hote hi banks.json direct RAM me load ho jayegi
BANKS_DATA = {}
json_file_path = os.path.join(os.path.dirname(__file__), "banks.json")

if os.path.exists(json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        BANKS_DATA = json.load(f)
    print(f"Loaded {len(BANKS_DATA)} banks successfully into memory.")
else:
    print("Warning: banks.json not found!")

RAPIDAPI_SECRET = "DISABLED"

def verify_gateway(secret_header: Optional[str]):
    if RAPIDAPI_SECRET != "DISABLED" and secret_header != RAPIDAPI_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Unauthorized: Call must originate via RapidAPI Gateway"
        )

@app.get("/")
def home():
    return {
        "status": "online", 
        "service": "India Financial Verification API",
        "total_banks": len(BANKS_DATA)
    }

# 1. Bank Details & Rails Verification (Pure RAM Lookup)
@app.get("/api/v1/bank/{ifsc_or_code}")
def bank_lookup(ifsc_or_code: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    bank_prefix = ifsc_or_code.strip()[:4].upper()

    bank = BANKS_DATA.get(bank_prefix)
    if not bank:
        raise HTTPException(status_code=404, detail=f"Bank code '{bank_prefix}' not found")

    return {
        "success": True,
        "data": {
            "bank_code": bank.get("code"),
            "bank_type": bank.get("type"),
            "sample_ifsc": bank.get("ifsc"),
            "micr": bank.get("micr"),
            "iin": bank.get("iin"),
            "payment_rails": {
                "upi": bool(bank.get("upi", False)),
                "ach_credit": bool(bank.get("ach_credit", False)),
                "ach_debit": bool(bank.get("ach_debit", False)),
                "apbs": bool(bank.get("apbs", False)),
                "nach_debit": bool(bank.get("nach_debit", False))
            }
        }
    }

# 2. Card IIN / BIN Lookup
@app.get("/api/v1/card/bin/{iin}")
def card_bin_lookup(iin: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    clean_iin = iin.strip()[:6]

    for code, bank in BANKS_DATA.items():
        if bank.get("iin") == clean_iin:
            return {
                "success": True,
                "iin": clean_iin,
                "bank_code": bank.get("code"),
                "bank_type": bank.get("type"),
                "upi_supported": bool(bank.get("upi", False))
            }

    raise HTTPException(status_code=404, detail="IIN/BIN not recognized")

# 3. PAN Verification
@app.get("/api/v1/verify/pan/{pan}")
def verify_pan(pan: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    clean_pan = pan.strip().upper()

    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", clean_pan):
        return {"success": True, "valid": False, "message": "Invalid PAN syntax"}

    entity_map = {
        'C': "Company", 'P': "Individual / Person", 'H': "HUF",
        'F': "Partnership / LLP", 'A': "AOP", 'T': "Trust",
        'B': "BOI", 'L': "Local Authority", 'J': "Artificial Juridical Person", 'G': "Government Agency"
    }

    return {
        "success": True,
        "valid": True,
        "pan": clean_pan,
        "entity_type": entity_map.get(clean_pan[3], "Other Entity"),
        "holder_initial": clean_pan[4]
    }

# 4. GSTIN Verification
@app.get("/api/v1/verify/gstin/{gstin}")
def verify_gstin(gstin: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    clean_gst = gstin.strip().upper()

    gst_regex = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    if not re.match(gst_regex, clean_gst):
        return {"success": True, "valid": False, "message": "Invalid GSTIN pattern"}

    return {
        "success": True,
        "valid": True,
        "gstin": clean_gst,
        "state_code": clean_gst[:2],
        "embedded_pan": clean_gst[2:12],
        "entity_number": clean_gst[12],
        "checksum": clean_gst[14]
    }
