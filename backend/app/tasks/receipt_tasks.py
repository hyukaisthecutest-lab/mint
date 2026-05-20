from __future__ import annotations
from app.core.celery_app import celery_app


@celery_app.task(name="scan_receipt", bind=True, max_retries=2, default_retry_delay=5)
def scan_receipt(self, key: str, content_type: str) -> dict:
    """Scan a receipt or bill from local storage using AWS Textract, then delete the file."""
    from app.core.textract import scan_receipt as textract_scan
    from app.core.s3 import delete_receipt

    try:
        result = textract_scan(key)
        return {"ok": True, "data": result.model_dump(mode="json")}
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"ok": False, "error": str(exc)}
    finally:
        delete_receipt(key)
