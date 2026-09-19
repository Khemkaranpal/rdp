import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, status
import pymysql

app = FastAPI(
    title="India Financial & Banking Rails API",
    description="Fast validation for Indian Banking, GST, PAN, and Postal codes",
    version="1.0.0"
)

# Database Connection Pool
def get_db():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="india_api_db",
        cursorclass=pymysql.cursors.DictCursor
    )

# Security verification (Local development me bypass karne ke liye "DISABLED" rakhein)
RAPIDAPI_SECRET = "DISABLED" 

def verify_gateway(secret_header: Optional[str]):
    if RAPIDAPI_SECRET != "DISABLED" and secret_header != RAPIDAPI_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Unauthorized: Call must originate via RapidAPI Gateway"
        )

# --- 1. Root & Health Check ---
@app.get("/")
def home():
    return {"status": "online", "service": "India Financial Verification API"}

# --- 2. Bank Details & Rails Verification ---
@app.get("/api/v1/bank/{ifsc_or_code}")
def bank_lookup(ifsc_or_code: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    bank_prefix = ifsc_or_code.strip()[:4].upper()

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM bank_masters WHERE code = %s LIMIT 1", (bank_prefix,))
            bank = cursor.fetchone()
            if not bank:
                raise HTTPException(status_code=404, detail="Bank prefix or IFSC not found")
            
            return {
                "success": True,
                "data": {
                    "bank_code": bank["code"],
                    "bank_type": bank["bank_type"],
                    "sample_ifsc": bank["sample_ifsc"],
                    "micr": bank["micr"],
                    "iin": bank["iin"],
                    "payment_rails": {
                        "upi": bool(bank["upi_supported"]),
                        "ach_credit": bool(bank["ach_credit"]),
                        "ach_debit": bool(bank["ach_debit"]),
                        "apbs": bool(bank["apbs"]),
                        "nach_debit": bool(bank["nach_debit"])
                    }
                }
            }
    finally:
        conn.close()

# --- 3. Card IIN / BIN Lookup ---
@app.get("/api/v1/card/bin/{iin}")
def card_bin_lookup(iin: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    clean_iin = iin.strip()[:6]

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM bank_masters WHERE iin = %s LIMIT 1", (clean_iin,))
            bank = cursor.fetchone()
            if not bank:
                raise HTTPException(status_code=404, detail="IIN/BIN not found")

            return {
                "success": True,
                "iin": clean_iin,
                "bank_code": bank["code"],
                "bank_type": bank["bank_type"],
                "upi_supported": bool(bank["upi_supported"])
            }
    finally:
        conn.close()

# --- 4. PAN Structural & Entity Validation ---
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

# --- 5. GSTIN Structure & State Breakdown ---
@app.get("/api/v1/verify/gstin/{gstin}")
def verify_gstin(gstin: str, x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    verify_gateway(x_rapidapi_proxy_secret)
    clean_gst = gstin.strip().upper()

    # Standard 15-character GST format
    gst_regex = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    if not re.match(gst_regex, clean_gst):
        return {"success": True, "valid": False, "message": "Invalid GSTIN pattern"}

    state_code = clean_gst[:2]
    associated_pan = clean_gst[2:12]

    return {
        "success": True,
        "valid": True,
        "gstin": clean_gst,
        "state_code": state_code,
        "embedded_pan": associated_pan,
        "entity_number": clean_gst[12],
        "checksum": clean_gst[14]
    }