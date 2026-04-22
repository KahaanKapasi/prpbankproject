"""
Seed script — truncates all tables and reinserts rich demo data.
Run: python seed.py
"""
import os
import random
import secrets
from datetime import date, timedelta, datetime
from decimal import Decimal

import bcrypt
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from demo_personas import PERSONAS

load_dotenv()

DB_URL = (os.getenv("DATABASE_URL") or "").strip()


def conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.DictCursor)


def hpw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def acct():
    return "PRPB" + str(random.randint(10000000, 99999999))


def ref():
    return secrets.token_hex(6).upper()


def days_ago(n, hour=10, minute=0):
    d = datetime.now() - timedelta(days=n)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


def main():
    db = conn()
    cur = db.cursor()

    print("Truncating all tables...")
    cur.execute("""
        TRUNCATE TABLE audit_log, approval_queue, feature_flags, fx_rates, stocks, config,
        cheques, transfers, budgets, goals, investments, cards, bills, loans,
        transactions, users RESTART IDENTITY CASCADE
    """)

    print("Inserting users...")
    user_ids = {}
    for p in PERSONAS:
        cur.execute(
            """INSERT INTO users (username, full_name, email, phone, password_hash, balance, savings_balance,
               account_number, role, status, kyc_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE','VERIFIED') RETURNING id""",
            (p["username"], p["full_name"], p["email"], p["phone"],
             hpw(p["password"]), p["wallet"], p["savings"], acct(), p["role"]),
        )
        user_ids[p["username"]] = cur.fetchone()[0]

    alice, bob, carol, dev, eve = (
        user_ids["alice"], user_ids["bob"], user_ids["carol"],
        user_ids["dev"], user_ids["eve"],
    )

    print("Inserting config...")
    defaults = [
        ("loan_interest_rate", "10.5", "rates", "Annual loan interest rate (%)"),
        ("fd_rate", "6.5", "rates", "Fixed deposit annual return (%)"),
        ("bonds_rate", "7.5", "rates", "Bond annual return (%)"),
        ("mf_rate", "11.0", "rates", "Mutual fund annual return (%)"),
        ("neft_fee", "5.00", "fees", "NEFT flat fee (INR)"),
        ("intl_flat_fee", "50.00", "fees", "International transfer flat fee (INR)"),
        ("intl_spread_pct", "1.0", "fees", "International transfer spread (%)"),
        ("daily_withdraw_limit", "50000", "limits", "Max daily withdrawal (INR)"),
        ("high_value_threshold", "500000", "limits", "Amount requiring admin approval"),
        ("bill_due_days", "7", "windows", "Days until bill due date"),
        ("require_loan_approval", "true", "features", "Loans require admin approval"),
        ("demo_mode", "true", "features", "Show demo-credentials panel on login"),
    ]
    cur.executemany(
        "INSERT INTO config (key,value,category,description) VALUES (%s,%s,%s,%s)",
        defaults,
    )

    print("Inserting FX rates...")
    fx = [("USD","INR",83.45), ("EUR","INR",90.12), ("GBP","INR",105.60), ("AED","INR",22.70)]
    cur.executemany("INSERT INTO fx_rates (base,quote,rate) VALUES (%s,%s,%s)", fx)

    print("Inserting stocks...")
    stx = [
        ("TechCorp","TechCorp Ltd",102.40,1.2),
        ("GreenEnergy","GreenEnergy Ltd",198.75,-0.8),
        ("FinBank","FinBank Ltd",154.10,0.5),
        ("InfraBuild","InfraBuild Ltd",76.20,-1.5),
    ]
    cur.executemany("INSERT INTO stocks (symbol,name,price,day_change) VALUES (%s,%s,%s,%s)", stx)

    print("Inserting feature flags...")
    flags = [
        ("enable_international_transfers", True, "Allow international transfers"),
        ("enable_cheques", True, "Allow cheque issuance"),
        ("enable_loans", True, "Allow loan applications"),
        ("enable_stocks", True, "Allow stock purchases"),
        ("enable_neft", True, "Allow NEFT transfers"),
        ("enable_bills", True, "Allow bill management"),
        ("enable_investments", True, "Allow FD/Bonds/MF investments"),
    ]
    cur.executemany("INSERT INTO feature_flags (key,enabled,description) VALUES (%s,%s,%s)", flags)

    def txn(uid, ttype, amount, desc, cat="", chan="", ref_id=None, ts=None):
        cur.execute(
            """INSERT INTO transactions (user_id,type,amount,description,category,channel,reference_id,timestamp)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uid, ttype, amount, desc, cat, chan, ref_id or ref(), ts or days_ago(random.randint(1,60))),
        )

    print("Seeding alice transactions...")
    txn(alice, "DEPOSIT", 95000, "Salary credit", "income", "bank", ts=days_ago(58, 9, 0))
    txn(alice, "DEPOSIT", 95000, "Salary credit", "income", "bank", ts=days_ago(28, 9, 0))
    txn(alice, "WITHDRAWAL", 15000, "Rent payment", "expense", "online", ts=days_ago(55))
    txn(alice, "UPI_TRANSFER", 2400, "Electricity bill", "bills", "upi", ts=days_ago(50))
    txn(alice, "UPI_TRANSFER", 450, "Coffee — Cafe Coffee Day", "food", "upi", ts=days_ago(48))
    txn(alice, "UPI_TRANSFER", 1850, "Grocery — BigBasket", "food", "upi", ts=days_ago(45))
    txn(alice, "BILL_PAYMENT", 399, "Mobile bill", "bills", "online", ts=days_ago(40))
    txn(alice, "UPI_TRANSFER", 3200, "Online shopping — Myntra", "shopping", "upi", ts=days_ago(38))
    txn(alice, "WITHDRAWAL", 15000, "Rent payment", "expense", "online", ts=days_ago(25))
    txn(alice, "UPI_TRANSFER", 1200, "Grocery — DMart", "food", "upi", ts=days_ago(20))
    txn(alice, "UPI_TRANSFER", 800, "Restaurant — Zomato", "food", "upi", ts=days_ago(15))
    txn(alice, "UPI_TRANSFER", 2800, "Shopping — Amazon", "shopping", "upi", ts=days_ago(12))
    txn(alice, "GOAL_CONTRIBUTION", 5000, "Goa trip goal", "savings", ts=days_ago(10))
    txn(alice, "INVESTMENT_PURCHASE", 25000, "FD investment", "investments", ts=days_ago(8))
    txn(alice, "UPI_TRANSFER", 199, "Netflix subscription", "entertainment", "upi", ts=days_ago(5))
    txn(alice, "BILL_PAYMENT", 999, "Internet bill", "bills", "online", ts=days_ago(3))

    print("Seeding bob transactions...")
    txn(bob, "DEPOSIT", 60000, "Salary credit", "income", "bank", ts=days_ago(58, 9, 0))
    txn(bob, "LOAN_DISBURSEMENT", 200000, "Loan #1 disbursed", "income", ts=days_ago(50))
    txn(bob, "LOAN_REPAYMENT", 30000, "Loan repayment", "expense", ts=days_ago(45))
    txn(bob, "WITHDRAWAL", 12000, "Rent payment", "expense", ts=days_ago(42))
    txn(bob, "LOAN_REPAYMENT", 30000, "Loan repayment", "expense", ts=days_ago(35))
    txn(bob, "DEPOSIT", 60000, "Salary credit", "income", "bank", ts=days_ago(28, 9, 0))
    txn(bob, "LOAN_REPAYMENT", 30000, "Loan repayment", "expense", ts=days_ago(20))
    txn(bob, "UPI_TRANSFER", 1800, "Grocery", "food", "upi", ts=days_ago(15))
    txn(bob, "LOAN_REPAYMENT", 30000, "Loan repayment", "expense", ts=days_ago(10))
    txn(bob, "UPI_TRANSFER", 600, "Mobile recharge", "bills", "upi", ts=days_ago(5))

    print("Seeding carol transactions...")
    txn(carol, "DEPOSIT", 200000, "Business income", "income", "bank", ts=days_ago(60, 9, 0))
    txn(carol, "DEPOSIT", 200000, "Business income", "income", "bank", ts=days_ago(30, 9, 0))
    txn(carol, "INVESTMENT_PURCHASE", 100000, "FD investment", "investments", ts=days_ago(55))
    txn(carol, "INVESTMENT_PURCHASE", 150000, "Bonds investment", "investments", ts=days_ago(50))
    txn(carol, "INVESTMENT_PURCHASE", 100000, "MF investment", "investments", ts=days_ago(45))
    txn(carol, "STOCK_PURCHASE", 10240, "TechCorp 100 shares", "investments", ts=days_ago(40))
    txn(carol, "STOCK_PURCHASE", 19875, "GreenEnergy 100 shares", "investments", ts=days_ago(35))
    txn(carol, "STOCK_PURCHASE", 15410, "FinBank 100 shares", "investments", ts=days_ago(30))
    txn(carol, "BILL_PAYMENT", 4200, "Electricity", "bills", ts=days_ago(20))
    txn(carol, "UPI_TRANSFER", 2100, "Restaurant", "food", "upi", ts=days_ago(10))
    txn(carol, "UPI_TRANSFER", 5800, "Shopping", "shopping", "upi", ts=days_ago(5))

    print("Seeding loans...")
    cur.execute(
        """INSERT INTO loans (user_id, principal, interest_rate, tenure_months, emi, total_owed, amount_paid, status, purpose, next_due_date, timestamp)
           VALUES (%s, 200000, 10.5, 24, 9268.17, 222436.08, 165000, 'ACTIVE', 'Home renovation', %s, %s)""",
        (bob, date.today() + timedelta(days=5), days_ago(50)),
    )
    cur.execute(
        """INSERT INTO loans (user_id, principal, interest_rate, tenure_months, emi, total_owed, amount_paid, status, purpose, timestamp)
           VALUES (%s, 50000, 10.5, 12, 4408.14, 52897.68, 52897.68, 'CLEARED', 'Emergency', %s)""",
        (bob, days_ago(200)),
    )
    cur.execute(
        """INSERT INTO loans (user_id, principal, interest_rate, tenure_months, emi, total_owed, amount_paid, status, purpose, timestamp)
           VALUES (%s, 500000, 10.5, 36, 16134.52, 580842.72, 0, 'PENDING_APPROVAL', 'Business expansion', %s) RETURNING id""",
        (alice, days_ago(2)),
    )
    alice_loan_id = cur.fetchone()[0]
    import json
    cur.execute(
        "INSERT INTO approval_queue (type, payload_json, requester_id, amount, reference_id, created_at) VALUES ('LOAN',%s,%s,%s,%s,%s)",
        (json.dumps({"loan_id": alice_loan_id, "principal": "500000", "purpose": "Business expansion"}), alice, 500000, ref(), days_ago(2)),
    )

    print("Seeding bills...")
    cur.execute(
        "INSERT INTO bills (user_id,bill_type,amount,due_date,status,paid_at) VALUES (%s,'ELECTRICITY',2400,%s,'PAID',%s)",
        (alice, date.today() - timedelta(days=30), days_ago(50)),
    )
    cur.execute(
        "INSERT INTO bills (user_id,bill_type,amount,due_date,status,paid_at) VALUES (%s,'MOBILE',399,%s,'PAID',%s)",
        (alice, date.today() - timedelta(days=15), days_ago(40)),
    )
    cur.execute(
        "INSERT INTO bills (user_id,bill_type,amount,due_date,status) VALUES (%s,'INTERNET',999,%s,'PENDING')",
        (alice, date.today() + timedelta(days=3)),
    )
    cur.execute(
        "INSERT INTO bills (user_id,bill_type,amount,due_date,status) VALUES (%s,'DTH',350,%s,'OVERDUE')",
        (alice, date.today() - timedelta(days=5)),
    )
    for btype, amt in [("ELECTRICITY", 3800), ("RENT", 18000), ("MOBILE", 599)]:
        cur.execute(
            "INSERT INTO bills (user_id,bill_type,amount,due_date,status) VALUES (%s,%s,%s,%s,'PENDING')",
            (bob, btype, amt, date.today() + timedelta(days=random.randint(1, 10))),
        )
    cur.execute(
        "INSERT INTO bills (user_id,bill_type,amount,due_date,status) VALUES (%s,'ELECTRICITY',4200,%s,'PENDING')",
        (carol, date.today() + timedelta(days=7)),
    )

    print("Seeding cards...")
    for uid, ctype, network, suffix in [
        (alice, "DEBIT", "VISA", "4321"),
        (bob, "DEBIT", "MASTERCARD", "5678"),
        (bob, "CREDIT", "VISA", "9012"),
        (carol, "DEBIT", "VISA", "1111"),
        (carol, "CREDIT", "MASTERCARD", "2222"),
        (carol, "VIRTUAL", "RUPAY", "3333"),
    ]:
        num = "4" + "".join([str(random.randint(0,9)) for _ in range(11)]) + suffix
        cur.execute(
            "INSERT INTO cards (user_id,card_number,holder_name,card_type,network,status,expiry_date) VALUES (%s,%s,(SELECT full_name FROM users WHERE id=%s),%s,%s,'ACTIVE','2030-12-31')",
            (uid, num, uid, ctype, network),
        )
    # Bob's blocked credit
    cur.execute("UPDATE cards SET status='BLOCKED' WHERE user_id=%s AND card_type='CREDIT'", (bob,))

    print("Seeding investments...")
    today = date.today()
    for uid, itype, amt, qty, price, mat_days in [
        (carol, "FD", 100000, 0, 0, 365),
        (carol, "BONDS", 150000, 0, 0, 365),
        (carol, "MF", 100000, 0, 0, 365),
        (carol, "TechCorp", 10240, 100, 102.40, 0),
        (carol, "GreenEnergy", 19875, 100, 198.75, 0),
        (carol, "FinBank", 15410, 100, 154.10, 0),
        (alice, "FD", 25000, 0, 0, 365),
        (alice, "MF", 15000, 0, 0, 365),
    ]:
        safe = itype in ("FD", "BONDS", "MF")
        rate_map = {"FD": 0.065, "BONDS": 0.075, "MF": 0.11}
        if safe:
            returns = round(amt * rate_map[itype], 2)
            cur_val = amt
            mat = today + timedelta(days=mat_days)
        else:
            returns = 0
            cur_val = qty * price
            mat = None
        cur.execute(
            "INSERT INTO investments (user_id,type,amount,quantity,unit_price_at_buy,returns,current_value,maturity_date,timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, itype, amt, qty, price, returns, cur_val, mat, days_ago(random.randint(30,55))),
        )

    print("Seeding goals...")
    cur.execute(
        "INSERT INTO goals (user_id,goal_name,target_amount,saved_amount,deadline) VALUES (%s,'Vacation to Goa',50000,32000,%s)",
        (alice, today + timedelta(days=60)),
    )
    cur.execute(
        "INSERT INTO goals (user_id,goal_name,target_amount,saved_amount) VALUES (%s,'Emergency Fund',100000,45000)",
        (alice,),
    )
    cur.execute(
        "INSERT INTO goals (user_id,goal_name,target_amount,saved_amount,deadline) VALUES (%s,'House Down Payment',2000000,850000,%s)",
        (carol, today + timedelta(days=730)),
    )

    print("Seeding budgets...")
    for uid, cat, limit, spent in [
        (alice, "Food", 8000, 5400),
        (alice, "Travel", 5000, 4800),
        (alice, "Shopping", 6000, 6300),
        (alice, "Entertainment", 3000, 450),
    ]:
        cur.execute(
            "INSERT INTO budgets (user_id,category,monthly_limit,spent) VALUES (%s,%s,%s,%s)",
            (uid, cat, limit, spent),
        )

    print("Seeding transfers...")
    for sid, rinfo, amt, ttype in [
        (alice, "bob", 5000, "BANK"),
        (alice, "name@okaxis", 1200, "UPI"),
        (bob, "alice", 3000, "NEFT"),
        (carol, "USD", 50000, "INTERNATIONAL"),
    ]:
        cur.execute(
            "INSERT INTO transfers (sender_id,receiver_info,amount,type,reference_id,timestamp) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_ids.get(sid, sid), rinfo, amt, ttype, ref(), days_ago(random.randint(5,30))),
        )

    print("Seeding pending cheque (bob → eve)...")
    # Deduct from bob for the fund hold
    cur.execute("UPDATE users SET balance=balance-15000 WHERE id=%s", (bob,))
    cur.execute(
        "INSERT INTO cheques (issuer_id,receiver_name,receiver_id,cheque_number,amount,funds_locked,status,issued_at) VALUES (%s,'eve',%s,%s,15000,TRUE,'PENDING',%s)",
        (bob, eve, "CHQ" + str(random.randint(100000,999999)), days_ago(3)),
    )

    print("Seeding audit log...")
    cur.execute(
        "INSERT INTO audit_log (admin_id,action,target_type,target_id,before_json,after_json) VALUES (%s,'APPROVE_LOAN','loan',2,'PENDING_APPROVAL','ACTIVE')",
        (user_ids["admin"],),
    )

    db.commit()
    db.close()
    print("Done! Seed complete.")
    print("\nDemo credentials:")
    for p in PERSONAS:
        print(f"  {p['username']:10} / {p['password']:10} — {p['hint']}")


if __name__ == "__main__":
    main()
