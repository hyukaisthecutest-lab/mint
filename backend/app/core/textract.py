from __future__ import annotations
import re
import logging
from datetime import date, datetime
from decimal import Decimal
import boto3
from app.core.config import settings

logger = logging.getLogger("mint.textract")

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Food & Drink": ["restaurant", "cafe", "coffee", "starbucks", "mcdonald", "pizza", "burger",
                     "sushi", "bar", "grill", "diner", "kitchen", "bistro", "eatery", "wendy",
                     "subway", "chipotle", "taco", "donut", "bakery"],
    "Groceries": ["grocery", "supermarket", "walmart", "target", "kroger", "safeway",
                  "trader joe", "whole foods", "aldi", "costco", "publix", "market", "fresh"],
    "Transportation": ["uber", "lyft", "taxi", "gas station", "fuel", "exxon", "shell",
                       "chevron", "bp ", "parking", "transit", "airline", "delta", "united",
                       "southwest", "spirit", "amtrak", "metro"],
    "Health & Fitness": ["pharmacy", "cvs", "walgreens", "rite aid", "hospital", "clinic",
                         "doctor", "dentist", "gym", "fitness", "health", "medical"],
    "Entertainment": ["cinema", "theater", "theatre", "movie", "amc ", "regal", "concert",
                      "ticketmaster", "netflix", "spotify", "hulu", "disney"],
    "Bills & Utilities": ["electric", "water", "gas bill", "internet", "phone", "utility",
                          "verizon", "at&t", "comcast", "xfinity", "t-mobile", "sprint",
                          "pg&e", "con ed", "duke energy"],
}


def _guess_category(merchant: str | None, item_names: list[str]) -> str:
    text = " ".join(filter(None, [merchant] + item_names)).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Shopping"


def _parse_decimal(s: str | None) -> Decimal | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", s.replace(",", ""))
    try:
        return Decimal(cleaned) if cleaned else None
    except Exception:
        return None


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y",
                "%m-%d-%Y", "%d-%m-%Y", "%m/%d/%y", "%b. %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _get_client():
    return boto3.client(
        "textract",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def _parse_expense_response(resp: dict):
    from app.schemas.transaction import ReceiptScanResponse, ReceiptLineItem

    docs = resp.get("ExpenseDocuments", [])
    if not docs:
        return ReceiptScanResponse(description="", category="Shopping", items=[])

    doc = docs[0]

    summary: dict[str, str] = {}
    for field in doc.get("SummaryFields", []):
        key = field.get("Type", {}).get("Text", "")
        val = field.get("ValueDetection", {}).get("Text")
        if key and val:
            summary[key] = val

    merchant = summary.get("VENDOR_NAME")
    tx_date = _parse_date(summary.get("INVOICE_RECEIPT_DATE"))
    total = _parse_decimal(summary.get("TOTAL"))
    tax = _parse_decimal(summary.get("TAX"))
    tip = _parse_decimal(summary.get("GRATUITY") or summary.get("TIP"))

    items = []
    item_names: list[str] = []
    for group in doc.get("LineItemGroups", []):
        for line in group.get("LineItems", []):
            fields: dict[str, str | None] = {
                f["Type"]["Text"]: f.get("ValueDetection", {}).get("Text")
                for f in line.get("LineItemExpenseFields", [])
                if f.get("Type", {}).get("Text")
            }
            name = fields.get("ITEM") or fields.get("PRODUCT_CODE")
            if not name:
                continue
            item_names.append(name)
            items.append(ReceiptLineItem(
                name=name,
                quantity=_parse_decimal(fields.get("QUANTITY")),
                unit_price=_parse_decimal(fields.get("UNIT_PRICE")),
                total=_parse_decimal(fields.get("PRICE")),
            ))

    category = _guess_category(merchant, item_names)
    description = f"{category} at {merchant}" if merchant else category

    return ReceiptScanResponse(
        merchant=merchant,
        amount=-total if total else None,
        description=description,
        category=category,
        transaction_date=tx_date,
        tax=tax,
        tip=tip,
        items=items,
    )


def scan_receipt(key: str):
    """Analyze a receipt or bill from local storage using Textract AnalyzeExpense."""
    from pathlib import Path
    image_bytes = (Path(settings.LOCAL_RECEIPTS_DIR) / key).read_bytes()
    resp = _get_client().analyze_expense(Document={"Bytes": image_bytes})
    return _parse_expense_response(resp)
