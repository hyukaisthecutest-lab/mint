from __future__ import annotations
import logging
import uuid
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.account import Account
from app.schemas.transaction import TransactionListResponse, TransactionCreate, ReceiptScanResponse
from app.dependencies import get_current_user
from typing import Optional

router = APIRouter(prefix="/transactions", tags=["transactions"])
logger = logging.getLogger("mint.transactions")

_ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
_MAX_BYTES = 10 * 1024 * 1024


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if category:
        query = query.filter(Transaction.category == category)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    total = query.count()
    transactions = (
        query.order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TransactionListResponse(transactions=transactions, total=total, page=page, page_size=page_size)


@router.post("/scan-receipt", response_model=ReceiptScanResponse)
async def scan_receipt(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    from app.core.s3 import upload_receipt, delete_receipt
    from app.core.textract import scan_receipt

    if image.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or PDF files are supported.")
    image_bytes = await image.read()
    if len(image_bytes) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="File must be under 10 MB.")

    content_type = image.content_type or "image/jpeg"
    suffix = content_type.split("/")[-1]
    s3_key = f"receipts/{current_user.id}/{uuid.uuid4()}.{suffix}"
    upload_receipt(s3_key, image_bytes, content_type)
    try:
        result = scan_receipt(s3_key)
    except Exception as e:
        logger.error("receipt_scan_error", extra={"extra": {"user_id": str(current_user.id), "error": str(e)}})
        raise HTTPException(status_code=500, detail="Could not extract data from receipt. Please try a clearer image.")
    finally:
        delete_receipt(s3_key)
    return result


@router.post("/scan-receipts/bulk")
async def scan_receipts_bulk(
    images: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    from app.core.s3 import upload_receipt
    from app.tasks.receipt_tasks import scan_receipt as scan_receipt_task

    if len(images) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per upload.")

    jobs = []
    for image in images:
        if image.content_type not in _ALLOWED_TYPES:
            jobs.append({"filename": image.filename, "job_id": None, "error": "Unsupported file type (JPEG, PNG, or PDF only)"})
            continue
        image_bytes = await image.read()
        if len(image_bytes) > _MAX_BYTES:
            jobs.append({"filename": image.filename, "job_id": None, "error": "File too large (max 10 MB)"})
            continue
        content_type = image.content_type or "image/jpeg"
        suffix = content_type.split("/")[-1]
        s3_key = f"receipts/{current_user.id}/{uuid.uuid4()}.{suffix}"
        upload_receipt(s3_key, image_bytes, content_type)
        task = scan_receipt_task.delay(s3_key, content_type)
        jobs.append({"filename": image.filename, "job_id": task.id, "error": None})

    return {"jobs": jobs}


@router.get("/scan-receipts/result/{job_id}")
def scan_receipt_result(job_id: str, current_user: User = Depends(get_current_user)):
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    if result.state in ("PENDING", "STARTED", "RETRY"):
        return {"status": "pending"}
    if result.state == "SUCCESS":
        data = result.result or {}
        if data.get("ok"):
            return {"status": "done", "data": data["data"]}
        return {"status": "error", "error": data.get("error", "Scan failed")}
    return {"status": "error", "error": str(result.info)}


@router.post("", response_model=dict)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(Account).filter(
        Account.id == payload.account_id,
        Account.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    txn = Transaction(
        account_id=payload.account_id,
        user_id=current_user.id,
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
        merchant=payload.merchant,
        transaction_date=payload.transaction_date,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return {"id": txn.id}
