import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.account import Account
from app.schemas.account import LinkAccountRequest, AccountResponse, SyncResponse
from app.services.fake_bank import seed_third_party_transactions
from app.tasks.sync_tasks import sync_account_transactions
from app.dependencies import get_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
def list_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Account).filter(Account.user_id == current_user.id, Account.is_active == True).all()


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def link_account(
    payload: LinkAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    external_id = f"ext_{current_user.id[:8]}_{uuid.uuid4().hex[:12]}"
    account = Account(
        user_id=current_user.id,
        name=payload.name,
        institution=payload.institution,
        account_type=payload.account_type,
        balance=payload.initial_balance,
        external_account_id=external_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    seed_third_party_transactions(db, external_id)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    account.is_active = False
    db.commit()


@router.post("/{account_id}/sync", response_model=SyncResponse)
def trigger_sync(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    task = sync_account_transactions.delay(account_id, current_user.id)
    return SyncResponse(task_id=task.id, message="Sync started")


@router.post("/sync-all", response_model=list[SyncResponse])
def sync_all_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.query(Account).filter(Account.user_id == current_user.id, Account.is_active == True).all()
    results = []
    for account in accounts:
        task = sync_account_transactions.delay(account.id, current_user.id)
        results.append(SyncResponse(task_id=task.id, message=f"Sync started for {account.name}"))
    return results
