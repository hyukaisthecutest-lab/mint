"""Simulates a third-party bank data provider (like Plaid)."""
import random
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.transaction import ThirdPartyTransaction

FAKE_TRANSACTIONS = [
    ("Starbucks", "Food & Drink", -5.75, -7.50),
    ("McDonald's", "Food & Drink", -8.25, -14.00),
    ("Chipotle", "Food & Drink", -11.50, -15.25),
    ("Whole Foods", "Groceries", -45.00, -120.00),
    ("Trader Joe's", "Groceries", -35.00, -90.00),
    ("Kroger", "Groceries", -50.00, -150.00),
    ("Amazon", "Shopping", -15.00, -200.00),
    ("Target", "Shopping", -25.00, -150.00),
    ("Walmart", "Shopping", -30.00, -200.00),
    ("Netflix", "Entertainment", -15.49, -15.49),
    ("Spotify", "Entertainment", -9.99, -9.99),
    ("Hulu", "Entertainment", -12.99, -12.99),
    ("Uber", "Transportation", -8.00, -35.00),
    ("Lyft", "Transportation", -10.00, -40.00),
    ("Shell Gas Station", "Transportation", -40.00, -75.00),
    ("AT&T", "Bills & Utilities", -85.00, -85.00),
    ("Comcast", "Bills & Utilities", -79.99, -79.99),
    ("Electric Company", "Bills & Utilities", -55.00, -120.00),
    ("Planet Fitness", "Health & Fitness", -24.99, -24.99),
    ("CVS Pharmacy", "Health & Fitness", -12.00, -80.00),
    ("Walgreens", "Health & Fitness", -15.00, -60.00),
    ("Direct Deposit", "Income", 2500.00, 5000.00),
    ("Freelance Payment", "Income", 500.00, 2000.00),
    ("Venmo Payment", "Transfer", -20.00, -200.00),
    ("Zelle Transfer", "Transfer", -50.00, -500.00),
]


def seed_third_party_transactions(db: Session, external_account_id: str, num_transactions: int = 45) -> None:
    today = date.today()
    records = []
    for _ in range(num_transactions):
        merchant, category, min_amt, max_amt = random.choice(FAKE_TRANSACTIONS)
        amount = round(random.uniform(min_amt, max_amt), 2)
        days_ago = random.randint(0, 90)
        records.append(
            ThirdPartyTransaction(
                external_account_id=external_account_id,
                amount=Decimal(str(amount)),
                description=f"{merchant} purchase" if amount < 0 else merchant,
                merchant=merchant,
                category=category,
                transaction_date=today - timedelta(days=days_ago),
                is_synced=False,
            )
        )
    db.add_all(records)
    db.commit()
