from decimal import Decimal
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction, ThirdPartyTransaction


@celery_app.task(bind=True, name="sync_account_transactions")
def sync_account_transactions(self, account_id: str, user_id: str):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {"status": "error", "message": "Account not found"}

        pending = (
            db.query(ThirdPartyTransaction)
            .filter(
                ThirdPartyTransaction.external_account_id == account.external_account_id,
                ThirdPartyTransaction.is_synced.is_(False),
            )
            .all()
        )

        synced_count = 0
        balance_delta = Decimal("0")
        for tp in pending:
            txn = Transaction(
                account_id=account_id,
                user_id=user_id,
                amount=tp.amount,
                description=tp.description,
                category=tp.category,
                merchant=tp.merchant,
                transaction_date=tp.transaction_date,
            )
            db.add(txn)
            tp.is_synced = True
            balance_delta += tp.amount
            synced_count += 1

        account.balance = account.balance + balance_delta
        db.commit()
        return {"status": "success", "synced": synced_count}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30, max_retries=3)
    finally:
        db.close()
