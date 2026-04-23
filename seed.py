#!/usr/bin/env python3
"""
PRP Bank — Standalone Demo Data Seeder

Usage:
    python seed.py              # Idempotent seed (skip if Kahaan exists)
    python seed.py --reset      # Wipe all data and re-seed
    python seed.py --verify     # Print row counts per table
"""
import os
import sys
import random
from datetime import datetime, timedelta, date

from dotenv import load_dotenv
import psycopg2
from werkzeug.security import generate_password_hash

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def verify():
    tables = [
        "users", "transactions", "loans", "bills", "cards",
        "investments", "goals", "budgets", "transfers", "cheques",
        "approvals", "audit_log", "feature_flags", "config", "fx_rates", "stocks",
    ]
    conn = get_conn()
    cur = conn.cursor()
    print("\nRow counts:")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:20s} {cur.fetchone()[0]}")
    conn.close()


def reset():
    conn = get_conn()
    cur = conn.cursor()
    for t in [
        "transfers", "cheques", "investments", "budgets", "goals",
        "cards", "bills", "loans", "transactions", "approvals",
        "audit_log", "feature_flags", "config", "fx_rates", "stocks", "users",
    ]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    print("All data cleared.")


def seed():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE name='Kahaan'")
    if cur.fetchone()[0] > 0:
        print("Data already seeded (Kahaan exists). Use --reset to wipe and re-seed.")
        conn.close()
        return

    now = datetime.now()

    # ── Users ──────────────────────────────────────────────────────────
    user_rows = [
        ("Kahaan",   generate_password_hash("B023B023"),   "kahaan@prpbank.in",
         "USER",  "Premier",  "active", 85000,  150000,
         "5001 0023 4821", "PRPB0001001", "Mumbai — Bandra West",  "BR001", now - timedelta(days=420)),
        ("Zaid",     generate_password_hash("B024B024"),   "zaid@prpbank.in",
         "ADMIN", "Private",  "active", 250000, 500000,
         "5001 0024 7702", "PRPB0001001", "Mumbai — Bandra West",  "BR001", now - timedelta(days=900)),
        ("Nishad",   generate_password_hash("B025B025"),   "nishad@prpbank.in",
         "USER",  "Standard", "active", 48000,  75000,
         "5001 0025 9067", "PRPB0001002", "Mumbai — Andheri East", "BR002", now - timedelta(days=120)),
        ("Siddhesh", generate_password_hash("PRP01PRP01"), "siddhesh@prpbank.in",
         "USER",  "Standard", "active", 120000, 200000,
         "5001 0001 1142", "PRPB0001003", "Mumbai — Thane West",   "BR003", now - timedelta(days=60)),
    ]
    user_ids = {}
    for u in user_rows:
        cur.execute(
            """INSERT INTO users
               (name,password,email,role,tier,status,balance,savings_balance,
                account_number,ifsc_code,branch,branch_code,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            u,
        )
        user_ids[u[0]] = cur.fetchone()[0]

    kid = user_ids["Kahaan"]
    zid = user_ids["Zaid"]
    nid = user_ids["Nishad"]
    sid = user_ids["Siddhesh"]

    # ── Transactions ───────────────────────────────────────────────────
    merchants = [
        ("Salary — PRP Ltd",      "Income",         "NEFT",   75000),
        ("Big Basket",            "Groceries",      "UPI",    -2340),
        ("BPCL Petrol",           "Fuel",           "Card",   -1850),
        ("Netflix India",         "Entertainment",  "Online", -649),
        ("Zomato",                "Dining",         "UPI",    -520),
        ("Ola",                   "Transport",      "Card",   -380),
        ("MSEB Electricity",      "Utilities",      "Online", -2100),
        ("Airtel Recharge",       "Telecom",        "UPI",    -599),
        ("Flipkart",              "Shopping",       "Online", -3200),
        ("Croma Electronics",     "Electronics",    "Card",   -7500),
        ("IndiGo Airlines",       "Travel",         "Card",   -4890),
        ("Chaayos",               "Dining",         "UPI",    -280),
        ("Amazon Prime",          "Subscriptions",  "Online", -1499),
        ("Uber",                  "Transport",      "Card",   -450),
        ("DMart",                 "Groceries",      "UPI",    -1870),
        ("IT Refund",             "Government",     "NEFT",   12400),
        ("Zerodha MF",            "Investments",    "Online", -10000),
        ("Rent — Bandra West",    "Housing",        "IMPS",   -25000),
        ("Swiggy",                "Dining",         "UPI",    -660),
        ("Myntra",                "Shopping",       "Online", -2100),
    ]
    for i, (desc, cat, ch, base_amt) in enumerate(merchants):
        for uid in [kid, nid, sid]:
            amt    = base_amt + random.randint(-200, 200)
            ts     = now - timedelta(days=i, hours=random.randint(0, 23))
            ttype  = "DEPOSIT" if amt > 0 else "WITHDRAWAL"
            if "Transfer" in cat or "Rent" in desc: ttype = "TRANSFER_OUT"
            elif "Salary" in desc or "Refund" in desc: ttype = "DEPOSIT"
            cur.execute(
                """INSERT INTO transactions
                   (user_id,type,amount,description,counterparty,category,channel,reference,status,timestamp)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uid, ttype, abs(amt), desc, desc, cat, ch,
                 f"REF{random.randint(100000,999999)}", "completed", ts),
            )

    # Salary for Zaid too
    for uid in [kid, zid]:
        cur.execute(
            """INSERT INTO transactions
               (user_id,type,amount,description,counterparty,category,channel,reference,status,timestamp)
               VALUES (%s,'DEPOSIT',75000,'Salary — PRP Ltd','PRP Ltd','Income','NEFT',%s,'completed',%s)""",
            (uid, f"REF{random.randint(100000,999999)}", now - timedelta(days=1)),
        )

    # ── Loans ──────────────────────────────────────────────────────────
    loans_data = [
        (kid, "Auto",     800000,  8.5,  60, 16423, 840000,  320000, 520000, "ACTIVE",  (now+timedelta(days=12)).date()),
        (kid, "Home",    4500000,  8.25, 240, 38540, 4725000, 605000, 4120000, "ACTIVE", (now+timedelta(days=3)).date()),
        (kid, "Personal", 200000, 11.5,  24,  9340, 210000,       0, 210000, "PENDING", (now+timedelta(days=30)).date()),
        (nid, "Personal", 100000, 10.0,  12,  8792, 105000,   35000,  70000, "ACTIVE",  (now+timedelta(days=15)).date()),
    ]
    for l in loans_data:
        cur.execute(
            """INSERT INTO loans
               (user_id,loan_type,principal,interest_rate,term_months,emi,total_owed,amount_paid,outstanding,status,next_due_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            l,
        )

    # ── Bills ──────────────────────────────────────────────────────────
    bills_data = [
        (kid, "MSEB Electricity",    "Utilities",     2840, (now+timedelta(days=2)).date(),  "PENDING"),
        (kid, "Airtel Broadband",    "Internet",      1299, (now+timedelta(days=5)).date(),  "SCHEDULED"),
        (kid, "HDFC Life Insurance", "Insurance",     4200, (now-timedelta(days=3)).date(),  "OVERDUE"),
        (kid, "MCGM Water",          "Utilities",      680, (now+timedelta(days=12)).date(), "PENDING"),
        (kid, "Amazon Prime",        "Subscriptions",  299, (now+timedelta(days=8)).date(),  "SCHEDULED"),
        (nid, "Tata Power",          "Utilities",     1950, (now+timedelta(days=4)).date(),  "PENDING"),
        (nid, "Jio Fiber",           "Internet",       999, (now-timedelta(days=1)).date(),  "OVERDUE"),
        (sid, "BEST Electricity",    "Utilities",     2200, (now+timedelta(days=6)).date(),  "PENDING"),
        (sid, "Netflix",             "Subscriptions",  649, (now+timedelta(days=10)).date(), "SCHEDULED"),
    ]
    for b in bills_data:
        cur.execute(
            "INSERT INTO bills (user_id,biller,category,amount,due_date,status) VALUES (%s,%s,%s,%s,%s,%s)",
            b,
        )

    # ── Cards ──────────────────────────────────────────────────────────
    cards_data = [
        (kid, "4012 8888 8888 4821", "RuPay",      "Debit",  "4821", "ACTIVE",       0,     0, date(2027, 8, 1)),
        (kid, "4916 3344 5566 1142", "Visa",        "Credit", "1142", "ACTIVE",  100000, 12450, date(2026, 11, 1)),
        (kid, "5199 9988 7755 7702", "Mastercard",  "Credit", "7702", "BLOCKED",  50000,  3200, date(2025, 2, 1)),
        (nid, "6521 0000 1111 9067", "RuPay",       "Debit",  "9067", "ACTIVE",       0,     0, date(2028, 3, 1)),
        (sid, "4532 6677 8899 5501", "Visa",        "Debit",  "5501", "ACTIVE",       0,     0, date(2027, 6, 1)),
        (sid, "5425 2334 3010 8832", "Mastercard",  "Credit", "8832", "ACTIVE",   75000,  8900, date(2027, 1, 1)),
    ]
    for c in cards_data:
        cur.execute(
            """INSERT INTO cards (user_id,card_number,brand,card_type,last4,status,card_limit,used,expiry_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            c,
        )

    # ── Investments ────────────────────────────────────────────────────
    inv_data = [
        (kid, "RELIANCE", "Reliance Industries", "Stock",       "Equity",  50, 2410, 2842, 142100, 21600,  0.82, None),
        (kid, "TCS",      "Tata Consultancy Svcs","Stock",      "Equity",  20, 3280, 4120,  82400, 16800, -0.34, None),
        (kid, "NIPPON-MF","Nippon India MF",      "Mutual Fund","MF",     200,   48,   62,  12400,  2800,  0.21, None),
        (kid, "GSEC-2031","G-Sec Bond 2031",      "Bond",       "Bond",    10, 99800, 98400, 984000,-14000,-0.18, date(2031, 6, 15)),
        (kid, "FD-12M",   "Fixed Deposit 12mo",   "FD",         "FD",       1,100000,100000,100000,     0,  0.00, (now+timedelta(days=220)).date()),
        (sid, "INFY",     "Infosys",              "Stock",       "Equity",  30, 1500, 1684,  50520,  5520,  1.21, None),
        (sid, "FD-24M",   "Fixed Deposit 24mo",   "FD",         "FD",       1,250000,250000,250000,     0,  0.00, (now+timedelta(days=540)).date()),
    ]
    for inv in inv_data:
        cur.execute(
            """INSERT INTO investments
               (user_id,symbol,inv_name,inv_type,category,shares,avg_cost,price,amount,returns,change_pct,maturity)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            inv,
        )

    # ── Budgets ────────────────────────────────────────────────────────
    budgets = [
        (kid,"Groceries",12000,9640),(kid,"Dining",6000,7210),(kid,"Transport",4000,2840),
        (kid,"Utilities",8000,6120),(kid,"Entertainment",3000,1380),(kid,"Shopping",10000,3720),
        (sid,"Groceries",10000,6500),(sid,"Transport",3000,2100),(sid,"Dining",5000,4200),
    ]
    for b in budgets:
        cur.execute("INSERT INTO budgets (user_id,category,monthly_limit,spent) VALUES (%s,%s,%s,%s)", b)

    # ── Goals ──────────────────────────────────────────────────────────
    goals = [
        (kid,"Emergency Fund",  500000, 275000, (now+timedelta(days=180)).date(),"ACTIVE"),
        (kid,"Home Down Payment",2000000,610000,(now+timedelta(days=540)).date(),"ACTIVE"),
        (kid,"Goa Trip",         80000,  51200, (now+timedelta(days=120)).date(),"ACTIVE"),
        (sid,"New Laptop",      150000,  45000, (now+timedelta(days=90)).date(), "ACTIVE"),
    ]
    for g in goals:
        cur.execute(
            "INSERT INTO goals (user_id,goal_name,target_amount,saved_amount,deadline,status) VALUES (%s,%s,%s,%s,%s,%s)",
            g,
        )

    # ── Approvals ──────────────────────────────────────────────────────
    approvals = [
        ("transfer","Kahaan",   now-timedelta(hours=1),  600000,"International wire to HSBC Singapore · Rahul Mehta","high","pending"),
        ("transfer","Siddhesh", now-timedelta(hours=3),  150000,"NEFT to HDFC Bank · Priya Sharma",                  "medium","pending"),
        ("loan",    "Nishad",   now-timedelta(days=1,hours=2),5000000,"Home loan · 20-yr · 8.5% p.a.",             "medium","pending"),
        ("card-limit","Kahaan", now-timedelta(hours=5),  500000,"Platinum Credit limit increase",                    "low","pending"),
        ("transfer","Siddhesh", now-timedelta(days=2),    99000,"IMPS · PRP Capital",                                "high","pending"),
    ]
    for a in approvals:
        cur.execute(
            "INSERT INTO approvals (kind,submitted_by,submitted_at,amount,detail,risk,status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            a,
        )

    # ── Audit Log ──────────────────────────────────────────────────────
    audit = [
        (now,                       "system",    "session.start",   "ops console",          None),
        (now-timedelta(hours=1),    "Zaid",      "user.login",      "Zaid",                 None),
        (now-timedelta(hours=3),    "system",    "rule.flag",       "txn high-value",        "₹6,00,000 SWIFT"),
        (now-timedelta(days=1),     "Zaid",      "config.update",   "transfer_limit_daily",  "500000 → 750000"),
        (now-timedelta(days=2,hours=5),"Zaid",   "approval.approve","apr_982",               "₹54,000 NEFT"),
    ]
    for a in audit:
        cur.execute("INSERT INTO audit_log (ts,actor,action,target,meta) VALUES (%s,%s,%s,%s,%s)", a)

    # ── Feature Flags ──────────────────────────────────────────────────
    flags = [
        ("intl_transfers",   "International Transfers",      "Allow SWIFT / international wires",           True),
        ("investments",      "Investments Module",           "Show Investments section to users",           True),
        ("loans_self_serve", "Self-Serve Loans",             "Users can apply for loans without RM",        True),
        ("cheque_issuance",  "Cheque Issuance",              "Issue cheques (places temp fund hold)",       True),
        ("high_value_review","High-Value Auto Review",       "Auto-route high-value transfers to approval", True),
        ("name_verify",      "Recipient Name Verify",        "Live name verification on NEFT/IMPS",         True),
    ]
    for f in flags:
        cur.execute(
            "INSERT INTO feature_flags (key,label,description,enabled) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            f,
        )

    # ── Config ─────────────────────────────────────────────────────────
    config = [
        ("transfer_limit_daily","500000"),("transfer_fee_domestic","5"),
        ("transfer_fee_international","500"),("high_value_threshold","500000"),
        ("overdraft_fee","500"),("savings_rate","6.5"),
        ("loan_rate_home","8.50"),("loan_rate_auto","9.50"),
        ("loan_rate_personal","12.00"),("loan_rate_education","10.00"),
    ]
    for c in config:
        cur.execute("INSERT INTO config (key,value) VALUES (%s,%s) ON CONFLICT DO NOTHING", c)

    # ── FX Rates ───────────────────────────────────────────────────────
    fx = [
        ("USD/INR",83.42),("EUR/INR",90.15),("GBP/INR",105.30),
        ("AED/INR",22.72),("SGD/INR",62.10),("JPY/INR",0.56),
    ]
    for pair, rate in fx:
        cur.execute("INSERT INTO fx_rates (pair,rate) VALUES (%s,%s) ON CONFLICT DO NOTHING", (pair,rate))

    # ── Stocks ─────────────────────────────────────────────────────────
    stocks = [
        ("RELIANCE","Reliance Industries",2842,0.82),
        ("TCS",     "TCS",               4120,-0.34),
        ("INFY",    "Infosys",           1684,1.21),
        ("HDFCBANK","HDFC Bank",         1847,-0.92),
        ("WIPRO",   "Wipro",              542,2.41),
        ("ICICIBANK","ICICI Bank",       1284,0.18),
    ]
    for s in stocks:
        cur.execute("INSERT INTO stocks (symbol,name,price,change_pct) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING", s)

    # ── Transfer History ───────────────────────────────────────────────
    transfers = [
        (kid,"Nishad (UPI)",       5000,"UPI","UPI",  f"UPI{random.randint(100000,999999)}", "COMPLETED",now-timedelta(days=3)),
        (kid,"Siddhesh (IMPS)",   12000,"IMPS","IMPS",f"IMPS{random.randint(100000,999999)}","COMPLETED",now-timedelta(days=5)),
        (sid,"Kahaan (NEFT)",      8000,"NEFT","NEFT",f"NEFT{random.randint(100000,999999)}","COMPLETED",now-timedelta(days=7)),
        (nid,"Kahaan (UPI)",       3000,"UPI","UPI",  f"UPI{random.randint(100000,999999)}", "COMPLETED",now-timedelta(days=2)),
    ]
    for t in transfers:
        cur.execute(
            "INSERT INTO transfers (sender_id,receiver_info,amount,type,channel,reference,status,timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            t,
        )

    conn.commit()
    conn.close()
    print("Seed complete!")
    print("  Kahaan   / B023B023  (USER)")
    print("  Zaid     / B024B024  (ADMIN)")
    print("  Nishad   / B025B025  (USER)")
    print("  Siddhesh / PRP01PRP01 (USER)")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify()
    elif "--reset" in sys.argv:
        reset()
        seed()
    else:
        seed()
