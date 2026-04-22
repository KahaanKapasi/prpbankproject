import os
import secrets
import random
from datetime import datetime, timedelta, date
from contextlib import contextmanager
from functools import wraps

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

db_url = (os.getenv("DATABASE_URL") or "").strip()

DEMO_USERS = [
    {
        "name": "Kahaan",
        "password": "B023B023",
        "role": "USER",
        "tier": "Premier",
        "email": "kahaan@prpbank.in",
        "account_number": "5001 0023 4821",
        "ifsc_code": "PRPB0001001",
        "branch": "Mumbai — Bandra West",
        "description": "Retail customer — Savings, FD, loans, UPI transfers, investments.",
    },
    {
        "name": "Zaid",
        "password": "B024B024",
        "role": "ADMIN",
        "tier": "Private",
        "email": "zaid@prpbank.in",
        "account_number": "5001 0024 7702",
        "ifsc_code": "PRPB0001001",
        "branch": "Mumbai — Bandra West",
        "description": "Bank operator — Approvals, configuration, audit, feature flags.",
    },
    {
        "name": "Nishad",
        "password": "B025B025",
        "role": "USER",
        "tier": "Standard",
        "email": "nishad@prpbank.in",
        "account_number": "5001 0025 9067",
        "ifsc_code": "PRPB0001002",
        "branch": "Mumbai — Andheri East",
        "description": "Retail customer — Savings account, bill payments.",
    },
    {
        "name": "Siddhesh",
        "password": "PRP01PRP01",
        "role": "USER",
        "tier": "Standard",
        "email": "siddhesh@prpbank.in",
        "account_number": "5001 0001 1142",
        "ifsc_code": "PRPB0001001",
        "branch": "Mumbai — Bandra West",
        "description": "Retail customer — Cards, transfers, personal finance.",
    },
]


# ── DB Helpers ────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = psycopg2.connect(db_url)
    try:
        yield conn
    finally:
        conn.close()


# ── User helpers ──────────────────────────────────────────────────────────────

def get_user(user_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, email, role, tier, status, balance,
                      savings_balance, account_number, ifsc_code, branch,
                      created_at
               FROM users WHERE id=%s""",
            (user_id,),
        )
        row = cur.fetchone()
    if row:
        return {
            "id": row[0], "name": row[1], "email": row[2],
            "role": row[3], "tier": row[4], "status": row[5],
            "balance": float(row[6] or 0),
            "savings": float(row[7] or 0),
            "account_number": row[8], "ifsc_code": row[9],
            "branch": row[10], "created_at": row[11],
        }
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "ADMIN":
            flash("Access denied.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def log_audit(conn, actor, action, target, meta=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (actor, action, target, meta) VALUES (%s,%s,%s,%s)",
        (actor, action, target, meta),
    )


def get_config(conn=None):
    def _fetch(c):
        cur = c.cursor()
        cur.execute("SELECT key, value FROM config")
        return {r[0]: r[1] for r in cur.fetchall()}
    if conn:
        return _fetch(conn)
    with get_db() as c:
        return _fetch(c)


def _is_high_value(amount, config=None, flags=None):
    """Return True if amount exceeds threshold and the review flag is on."""
    if config is None:
        config = get_config()
    if flags is None:
        flags = get_feature_flags()
    if not flags.get("high_value_review", False):
        return False
    threshold = float(config.get("high_value_threshold", "500000"))
    return amount >= threshold


def _create_approval(conn, user, amount, detail, kind="high_value_transfer"):
    cur = conn.cursor()
    risk = "HIGH" if amount >= 1000000 else "MEDIUM"
    cur.execute(
        """INSERT INTO approvals (kind, submitted_by, amount, detail, risk, status)
           VALUES (%s, %s, %s, %s, %s, 'pending')""",
        (kind, user["name"], amount, detail, risk),
    )
    conn.commit()


def feature_guard(flag_key):
    """Decorator: redirect to dashboard when a feature flag is disabled."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not flag_enabled(flag_key):
                flash("This feature is currently disabled.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Template Filters ──────────────────────────────────────────────────────────

@app.template_filter("inr")
def inr_filter(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value
    sign = "-" if n < 0 else ""
    n = abs(n)
    integer_part = int(n)
    decimal = f"{n - integer_part:.2f}"[1:]
    s = str(integer_part)
    if len(s) <= 3:
        return f"{sign}₹{s}{decimal}"
    result = s[-3:]
    s = s[:-3]
    while s:
        chunk = s[-2:] if len(s) >= 2 else s
        result = chunk + "," + result
        s = s[:-2]
    return f"{sign}₹{result}{decimal}"


@app.template_filter("datetimeformat")
def datetimeformat_filter(value, fmt="%d %b, %H:%M"):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(fmt)


@app.template_filter("dateformat")
def dateformat_filter(value, fmt="%d %b %Y"):
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(fmt)


def get_feature_flags(conn=None):
    def _fetch(c):
        cur = c.cursor()
        cur.execute("SELECT key, enabled FROM feature_flags")
        return {r[0]: r[1] for r in cur.fetchall()}
    if conn:
        return _fetch(conn)
    with get_db() as c:
        return _fetch(c)


def flag_enabled(key, flags=None):
    if flags is None:
        flags = get_feature_flags()
    return flags.get(key, True)


@app.context_processor
def inject_globals():
    flags = {}
    if "user_id" in session:
        try:
            flags = get_feature_flags()
        except Exception:
            pass
    return {
        "session_role": session.get("role", ""),
        "session_name": session.get("user_name", ""),
        "flags": flags,
    }


# ── Schema ────────────────────────────────────────────────────────────────────

def db_init():
    with get_db() as conn:
        cur = conn.cursor()

        # Check if schema is outdated (missing new columns). If so, drop and recreate.
        try:
            cur.execute("SELECT role FROM users LIMIT 0")
            cur.execute("SELECT description FROM transactions LIMIT 0")
            cur.execute("SELECT 1 FROM approvals LIMIT 0")
        except Exception:
            conn.rollback()
            # Old schema detected - drop everything and start fresh
            cur.execute("""
                DROP TABLE IF EXISTS transfers, cheques, investments, budgets, goals,
                    cards, bills, loans, transactions, approvals, audit_log,
                    feature_flags, config, fx_rates, stocks, users CASCADE
            """)
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                email TEXT,
                role VARCHAR(10) DEFAULT 'USER',
                tier VARCHAR(20) DEFAULT 'Standard',
                status VARCHAR(20) DEFAULT 'active',
                balance NUMERIC DEFAULT 0,
                savings_balance NUMERIC DEFAULT 0,
                account_number TEXT,
                ifsc_code TEXT DEFAULT 'PRPB0001001',
                branch TEXT DEFAULT 'Mumbai — Bandra West',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(50) NOT NULL,
                amount NUMERIC NOT NULL,
                description TEXT,
                counterparty TEXT,
                category TEXT,
                channel VARCHAR(20),
                reference TEXT,
                status VARCHAR(20) DEFAULT 'completed',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                loan_type VARCHAR(30) DEFAULT 'Personal',
                principal NUMERIC NOT NULL,
                interest_rate NUMERIC DEFAULT 5.0,
                term_months INTEGER DEFAULT 12,
                emi NUMERIC DEFAULT 0,
                total_owed NUMERIC NOT NULL,
                amount_paid NUMERIC DEFAULT 0,
                outstanding NUMERIC DEFAULT 0,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                next_due_date DATE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                biller TEXT,
                category TEXT,
                amount NUMERIC,
                due_date DATE,
                status VARCHAR(20) DEFAULT 'PENDING'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                card_number TEXT UNIQUE,
                brand VARCHAR(20) DEFAULT 'Visa',
                card_type VARCHAR(20) DEFAULT 'Debit',
                last4 TEXT,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                card_limit NUMERIC DEFAULT 0,
                used NUMERIC DEFAULT 0,
                expiry_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS investments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                symbol TEXT,
                inv_name TEXT,
                inv_type VARCHAR(30),
                category VARCHAR(20) DEFAULT 'Equity',
                shares NUMERIC DEFAULT 0,
                avg_cost NUMERIC DEFAULT 0,
                price NUMERIC DEFAULT 0,
                amount NUMERIC DEFAULT 0,
                returns NUMERIC DEFAULT 0,
                change_pct NUMERIC DEFAULT 0,
                maturity DATE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                goal_name TEXT,
                target_amount NUMERIC,
                saved_amount NUMERIC DEFAULT 0,
                deadline DATE,
                status VARCHAR(20) DEFAULT 'ACTIVE'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                category TEXT,
                monthly_limit NUMERIC,
                spent NUMERIC DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                receiver_info TEXT,
                amount NUMERIC,
                type VARCHAR(30),
                channel VARCHAR(20),
                reference TEXT,
                status VARCHAR(20) DEFAULT 'COMPLETED',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cheques (
                id SERIAL PRIMARY KEY,
                issuer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                receiver_name TEXT,
                amount NUMERIC,
                status VARCHAR(20) DEFAULT 'PENDING',
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id SERIAL PRIMARY KEY,
                kind VARCHAR(30),
                submitted_by TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount NUMERIC,
                detail TEXT,
                risk VARCHAR(10) DEFAULT 'low',
                status VARCHAR(20) DEFAULT 'pending'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actor TEXT,
                action TEXT,
                target TEXT,
                meta TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS feature_flags (
                key TEXT PRIMARY KEY,
                label TEXT,
                description TEXT,
                enabled BOOLEAN DEFAULT true
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS fx_rates (
                pair TEXT PRIMARY KEY,
                rate NUMERIC,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                price NUMERIC,
                change_pct NUMERIC
            )
        """)

        conn.commit()


# ── Seed Data ─────────────────────────────────────────────────────────────────

def seed_demo_data():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE name='Kahaan'")
        if cur.fetchone()[0] > 0:
            return

        now = datetime.now()

        user_rows = [
            ("Kahaan", generate_password_hash("B023B023"), "kahaan@prpbank.in",
             "USER", "Premier", "active", 85000, 150000,
             "5001 0023 4821", "PRPB0001001", "Mumbai — Bandra West",
             now - timedelta(days=420)),
            ("Zaid", generate_password_hash("B024B024"), "zaid@prpbank.in",
             "ADMIN", "Private", "active", 250000, 500000,
             "5001 0024 7702", "PRPB0001001", "Mumbai — Bandra West",
             now - timedelta(days=900)),
            ("Nishad", generate_password_hash("B025B025"), "nishad@prpbank.in",
             "USER", "Standard", "active", 48000, 75000,
             "5001 0025 9067", "PRPB0001002", "Mumbai — Andheri East",
             now - timedelta(days=120)),
            ("Siddhesh", generate_password_hash("PRP01PRP01"), "siddhesh@prpbank.in",
             "USER", "Standard", "active", 120000, 200000,
             "5001 0001 1142", "PRPB0001001", "Mumbai — Bandra West",
             now - timedelta(days=60)),
        ]

        user_ids = {}
        for u in user_rows:
            cur.execute(
                """INSERT INTO users
                   (name, password, email, role, tier, status, balance,
                    savings_balance, account_number, ifsc_code, branch, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                u,
            )
            user_ids[u[0]] = cur.fetchone()[0]

        kid = user_ids["Kahaan"]
        zid = user_ids["Zaid"]
        nid = user_ids["Nishad"]
        sid = user_ids["Siddhesh"]

        merchants = [
            ("Salary — PRP Ltd", "Income", "NEFT", 75000),
            ("Big Basket", "Groceries", "UPI", -2340),
            ("BPCL Petrol", "Fuel", "Card", -1850),
            ("Netflix India", "Entertainment", "Online", -649),
            ("Zomato", "Dining", "UPI", -520),
            ("Ola", "Transport", "Card", -380),
            ("MSEB Electricity", "Utilities", "Online", -2100),
            ("Airtel Recharge", "Telecom", "UPI", -599),
            ("Flipkart", "Shopping", "Online", -3200),
            ("Croma Electronics", "Electronics", "Card", -7500),
            ("IndiGo Airlines", "Travel", "Card", -4890),
            ("Chaayos", "Dining", "UPI", -280),
            ("Amazon Prime", "Subscriptions", "Online", -1499),
            ("Uber", "Transport", "Card", -450),
            ("DMart", "Groceries", "UPI", -1870),
            ("IT Refund", "Government", "NEFT", 12400),
            ("Zerodha MF", "Investments", "Online", -10000),
            ("Rent — Bandra West", "Housing", "IMPS", -25000),
            ("Swiggy", "Dining", "UPI", -660),
            ("Myntra", "Shopping", "Online", -2100),
        ]

        txn_statuses = ["completed"] * 17 + ["pending", "flagged", "failed"]

        for i, (desc, cat, ch, base_amt) in enumerate(merchants):
            for uid in [kid, nid, sid]:
                amt = base_amt + random.randint(-200, 200)
                ts = now - timedelta(days=i, hours=random.randint(0, 23))
                st = txn_statuses[i % len(txn_statuses)]
                ttype = "DEPOSIT" if amt > 0 else "WITHDRAWAL"
                if "Transfer" in cat or "Rent" in desc:
                    ttype = "TRANSFER_OUT"
                elif "Salary" in desc or "Refund" in desc:
                    ttype = "DEPOSIT"
                ref = f"REF{random.randint(100000, 999999)}"
                cur.execute(
                    """INSERT INTO transactions
                       (user_id, type, amount, description, counterparty,
                        category, channel, reference, status, timestamp)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (uid, ttype, abs(amt), desc, desc, cat, ch, ref, st, ts),
                )

        for uid in [kid, zid]:
            cur.execute(
                """INSERT INTO transactions
                   (user_id, type, amount, description, counterparty,
                    category, channel, reference, status, timestamp)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uid, "DEPOSIT", 75000, "Salary — PRP Ltd", "PRP Ltd",
                 "Income", "NEFT", f"REF{random.randint(100000,999999)}",
                 "completed", now - timedelta(days=1)),
            )

        loans_data = [
            (kid, "Auto", 800000, 8.5, 60, 16423, 840000, 320000, 520000, "ACTIVE",
             (now + timedelta(days=12)).date()),
            (kid, "Home", 4500000, 8.25, 240, 38540, 4725000, 605000, 4120000, "ACTIVE",
             (now + timedelta(days=3)).date()),
            (kid, "Personal", 200000, 11.5, 24, 9340, 210000, 0, 210000, "PENDING",
             (now + timedelta(days=30)).date()),
            (nid, "Personal", 100000, 10.0, 12, 8792, 105000, 35000, 70000, "ACTIVE",
             (now + timedelta(days=15)).date()),
        ]
        for l in loans_data:
            cur.execute(
                """INSERT INTO loans
                   (user_id, loan_type, principal, interest_rate, term_months,
                    emi, total_owed, amount_paid, outstanding, status, next_due_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                l,
            )

        bills_data = [
            (kid, "MSEB Electricity", "Utilities", 2840,
             (now + timedelta(days=2)).date(), "PENDING"),
            (kid, "Airtel Broadband", "Internet", 1299,
             (now + timedelta(days=5)).date(), "SCHEDULED"),
            (kid, "HDFC Life Insurance", "Insurance", 4200,
             (now - timedelta(days=3)).date(), "OVERDUE"),
            (kid, "MCGM Water", "Utilities", 680,
             (now + timedelta(days=12)).date(), "PENDING"),
            (kid, "Amazon Prime", "Subscriptions", 299,
             (now + timedelta(days=8)).date(), "SCHEDULED"),
            (nid, "Tata Power", "Utilities", 1950,
             (now + timedelta(days=4)).date(), "PENDING"),
            (nid, "Jio Fiber", "Internet", 999,
             (now - timedelta(days=1)).date(), "OVERDUE"),
            (sid, "BEST Electricity", "Utilities", 2200,
             (now + timedelta(days=6)).date(), "PENDING"),
            (sid, "Netflix", "Subscriptions", 649,
             (now + timedelta(days=10)).date(), "SCHEDULED"),
        ]
        for b in bills_data:
            cur.execute(
                """INSERT INTO bills
                   (user_id, biller, category, amount, due_date, status)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                b,
            )

        cards_data = [
            (kid, "4821 XXXX XXXX 4821", "RuPay", "Debit", "4821", "ACTIVE",
             0, 0, date(2027, 8, 1)),
            (kid, "1142 XXXX XXXX 1142", "Visa", "Credit", "1142", "ACTIVE",
             100000, 12450, date(2026, 11, 1)),
            (kid, "7702 XXXX XXXX 7702", "Mastercard", "Credit", "7702", "BLOCKED",
             50000, 3200, date(2025, 2, 1)),
            (nid, "9067 XXXX XXXX 9067", "RuPay", "Debit", "9067", "ACTIVE",
             0, 0, date(2028, 3, 1)),
            (sid, "1142 XXXX XXXX 5501", "Visa", "Debit", "5501", "ACTIVE",
             0, 0, date(2027, 6, 1)),
            (sid, "7702 XXXX XXXX 8832", "Mastercard", "Credit", "8832", "ACTIVE",
             75000, 8900, date(2027, 1, 1)),
        ]
        for c in cards_data:
            cur.execute(
                """INSERT INTO cards
                   (user_id, card_number, brand, card_type, last4, status,
                    card_limit, used, expiry_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                c,
            )

        inv_data = [
            (kid, "RELIANCE", "Reliance Industries", "Stock", "Equity",
             50, 2410, 2842, 142100, 21600, 0.82, None),
            (kid, "TCS", "Tata Consultancy Svcs", "Stock", "Equity",
             20, 3280, 4120, 82400, 16800, -0.34, None),
            (kid, "NIPPON-MF", "Nippon India MF", "Mutual Fund", "MF",
             200, 48, 62, 12400, 2800, 0.21, None),
            (kid, "GSEC-2031", "G-Sec Bond 2031", "Bond", "Bond",
             10, 99800, 98400, 984000, -14000, -0.18, date(2031, 6, 15)),
            (kid, "FD-12M", "Fixed Deposit 12mo", "FD", "FD",
             1, 100000, 100000, 100000, 0, 0, (now + timedelta(days=220)).date()),
            (sid, "INFY", "Infosys", "Stock", "Equity",
             30, 1500, 1684, 50520, 5520, 1.21, None),
            (sid, "FD-24M", "Fixed Deposit 24mo", "FD", "FD",
             1, 250000, 250000, 250000, 0, 0, (now + timedelta(days=540)).date()),
        ]
        for inv in inv_data:
            cur.execute(
                """INSERT INTO investments
                   (user_id, symbol, inv_name, inv_type, category,
                    shares, avg_cost, price, amount, returns, change_pct, maturity)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                inv,
            )

        budgets_data = [
            (kid, "Groceries", 12000, 9640),
            (kid, "Dining", 6000, 7210),
            (kid, "Transport", 4000, 2840),
            (kid, "Utilities", 8000, 6120),
            (kid, "Entertainment", 3000, 1380),
            (kid, "Shopping", 10000, 3720),
            (sid, "Groceries", 10000, 6500),
            (sid, "Transport", 3000, 2100),
            (sid, "Dining", 5000, 4200),
        ]
        for b in budgets_data:
            cur.execute(
                "INSERT INTO budgets (user_id, category, monthly_limit, spent) VALUES (%s,%s,%s,%s)",
                b,
            )

        goals_data = [
            (kid, "Emergency Fund", 500000, 275000,
             (now + timedelta(days=180)).date(), "ACTIVE"),
            (kid, "Home Down Payment", 2000000, 610000,
             (now + timedelta(days=540)).date(), "ACTIVE"),
            (kid, "Goa Trip", 80000, 51200,
             (now + timedelta(days=120)).date(), "ACTIVE"),
            (sid, "New Laptop", 150000, 45000,
             (now + timedelta(days=90)).date(), "ACTIVE"),
        ]
        for g in goals_data:
            cur.execute(
                """INSERT INTO goals
                   (user_id, goal_name, target_amount, saved_amount, deadline, status)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                g,
            )

        approvals_data = [
            ("transfer", "kahaan@prpbank.in", now - timedelta(hours=1),
             600000, "International wire to HSBC Singapore · Beneficiary: Rahul Mehta",
             "high", "pending"),
            ("transfer", "siddhesh@prpbank.in", now - timedelta(hours=3),
             150000, "NEFT to HDFC Bank · Priya Sharma",
             "medium", "pending"),
            ("loan", "nishad@prpbank.in", now - timedelta(days=1, hours=2),
             5000000, "Home loan · 20-yr · 8.5% p.a.",
             "medium", "pending"),
            ("card-limit", "kahaan@prpbank.in", now - timedelta(hours=5),
             500000, "Platinum Credit limit increase",
             "low", "pending"),
            ("transfer", "siddhesh@prpbank.in", now - timedelta(days=2),
             99000, "IMPS · PRP Capital (structured?)",
             "high", "pending"),
        ]
        for a in approvals_data:
            cur.execute(
                """INSERT INTO approvals
                   (kind, submitted_by, submitted_at, amount, detail, risk, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                a,
            )

        audit_data = [
            (now, "system", "session.start", "ops console", None),
            (now - timedelta(hours=1), "ops.admin", "user.login", "Zaid", None),
            (now - timedelta(hours=3), "system", "rule.flag",
             "txn high-value", "₹6,00,000 SWIFT"),
            (now - timedelta(days=1), "ops.admin", "config.update",
             "transfer_limit_daily", "500000 → 750000"),
            (now - timedelta(days=2, hours=5), "ops.admin", "approval.approve",
             "apr_982", "₹54,000 NEFT"),
        ]
        for a in audit_data:
            cur.execute(
                "INSERT INTO audit_log (ts, actor, action, target, meta) VALUES (%s,%s,%s,%s,%s)",
                a,
            )

        flags_data = [
            ("intl_transfers", "International Transfers",
             "Allow SWIFT / international wires", True),
            ("investments", "Investments Module",
             "Show Investments section to users", True),
            ("loans_self_serve", "Self-Serve Loans",
             "Users can apply for loans without RM", True),
            ("cheque_issuance", "Cheque Issuance",
             "Issue cheques (places temp fund hold)", True),
            ("high_value_review", "High-Value Auto Review",
             "Auto-route high-value transfers to approval queue", True),
            ("name_verify", "Recipient Name Verify",
             "Live name verification on NEFT/IMPS", True),
        ]
        for f in flags_data:
            cur.execute(
                "INSERT INTO feature_flags (key, label, description, enabled) VALUES (%s,%s,%s,%s)",
                f,
            )

        config_data = [
            ("transfer_limit_daily", "500000"),
            ("transfer_fee_domestic", "5"),
            ("transfer_fee_international", "500"),
            ("high_value_threshold", "500000"),
            ("overdraft_fee", "500"),
            ("savings_rate", "6.5"),
        ]
        for c in config_data:
            cur.execute("INSERT INTO config (key, value) VALUES (%s,%s)", c)

        fx_data = [
            ("USD/INR", 83.42), ("EUR/INR", 90.15), ("GBP/INR", 105.30),
            ("AED/INR", 22.72), ("SGD/INR", 62.10), ("JPY/INR", 0.56),
        ]
        for pair, rate in fx_data:
            cur.execute(
                "INSERT INTO fx_rates (pair, rate) VALUES (%s,%s)", (pair, rate),
            )

        stocks_data = [
            ("RELIANCE", "Reliance Industries", 2842, 0.82),
            ("TCS", "TCS", 4120, -0.34),
            ("INFY", "Infosys", 1684, 1.21),
            ("HDFCBANK", "HDFC Bank", 1847, -0.92),
            ("WIPRO", "Wipro", 542, 2.41),
            ("ICICIBANK", "ICICI Bank", 1284, 0.18),
        ]
        for s in stocks_data:
            cur.execute(
                "INSERT INTO stocks (symbol, name, price, change_pct) VALUES (%s,%s,%s,%s)",
                s,
            )

        transfers_data = [
            (kid, "Nishad (UPI)", 5000, "UPI", "UPI", f"UPI{random.randint(100000,999999)}",
             "COMPLETED", now - timedelta(days=3)),
            (kid, "Siddhesh (IMPS)", 12000, "IMPS", "IMPS", f"IMPS{random.randint(100000,999999)}",
             "COMPLETED", now - timedelta(days=5)),
            (sid, "Kahaan (NEFT)", 8000, "NEFT", "NEFT", f"NEFT{random.randint(100000,999999)}",
             "COMPLETED", now - timedelta(days=7)),
            (nid, "Kahaan (UPI)", 3000, "UPI", "UPI", f"UPI{random.randint(100000,999999)}",
             "COMPLETED", now - timedelta(days=2)),
        ]
        for t in transfers_data:
            cur.execute(
                """INSERT INTO transfers
                   (sender_id, receiver_info, amount, type, channel, reference, status, timestamp)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                t,
            )

        conn.commit()


def reset_demo_data():
    with get_db() as conn:
        cur = conn.cursor()
        for table in [
            "transfers", "cheques", "investments", "budgets", "goals",
            "cards", "bills", "loans", "transactions", "approvals",
            "audit_log", "feature_flags", "config", "fx_rates", "stocks", "users",
        ]:
            cur.execute(f"DELETE FROM {table}")
        conn.commit()
    seed_demo_data()


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("customer_id", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not password:
            flash("Customer ID and password are required.", "error")
            return render_template("login.html", demo_users=DEMO_USERS)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, password, role FROM users WHERE name=%s", (name,))
            row = cur.fetchone()

        if not row or not check_password_hash(row[2], password):
            flash("Invalid credentials. Please try again.", "error")
            return render_template("login.html", demo_users=DEMO_USERS)

        session["user_id"] = row[0]
        session["user_name"] = row[1]
        session["role"] = row[3]

        if row[3] == "ADMIN":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html", demo_users=DEMO_USERS)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not password:
            flash("Name and password are required.", "error")
            return render_template("register.html")

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE name=%s", (name,))
            if cur.fetchone():
                flash("Username already taken.", "error")
                return render_template("register.html")

            acct = f"5001 {random.randint(1000,9999)} {random.randint(1000,9999)}"
            cur.execute(
                """INSERT INTO users
                   (name, password, email, role, tier, status, balance,
                    savings_balance, account_number, ifsc_code, branch)
                   VALUES (%s,%s,%s,'USER','Standard','active',0,0,%s,'PRPB0001001','Mumbai — Bandra West')
                   RETURNING id""",
                (name, generate_password_hash(password), email or None, acct),
            )
            new_id = cur.fetchone()[0]
            conn.commit()

        session["user_id"] = new_id
        session["user_name"] = name
        session["role"] = "USER"
        flash("Account created successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── User Routes ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_user(session["user_id"])
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT type, amount, description, category, channel, status, timestamp, reference
               FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 8""",
            (user["id"],),
        )
        recent = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) FROM loans WHERE user_id=%s AND status='ACTIVE'",
            (user["id"],),
        )
        active_loans = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM bills WHERE user_id=%s AND status IN ('PENDING','OVERDUE')",
            (user["id"],),
        )
        pending_bills = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM investments WHERE user_id=%s",
            (user["id"],),
        )
        total_invested = float(cur.fetchone()[0])

        cur.execute(
            """SELECT biller, amount, due_date FROM bills
               WHERE user_id=%s AND status='OVERDUE' LIMIT 5""",
            (user["id"],),
        )
        overdue_bills = cur.fetchall()

        cur.execute(
            """SELECT card_number, brand, card_type, last4, status, card_limit, used, expiry_date
               FROM cards WHERE user_id=%s LIMIT 3""",
            (user["id"],),
        )
        cards = cur.fetchall()

    return render_template(
        "dashboard.html", user=user, recent=recent,
        active_loans=active_loans, pending_bills=pending_bills,
        total_invested=total_invested, overdue_bills=overdue_bills,
        cards=cards,
    )


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    user = get_user(session["user_id"])

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount <= 0:
            flash("Enter a valid amount.", "error")
        else:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user["id"]))
                cur.execute(
                    """INSERT INTO transactions
                       (user_id, type, amount, description, category, channel, reference, status)
                       VALUES (%s,'DEPOSIT',%s,'Cash Deposit','Deposit','Branch',%s,'completed')""",
                    (user["id"], amount, f"DEP{random.randint(100000,999999)}"),
                )
                conn.commit()
            flash(f"₹{amount:,.2f} deposited successfully!", "success")
        return redirect(url_for("deposit"))

    user = get_user(session["user_id"])
    return render_template("deposit.html", user=user)


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    user = get_user(session["user_id"])

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount <= 0:
            flash("Enter a valid amount.", "error")
        elif amount > user["balance"]:
            flash("Insufficient balance.", "error")
        else:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                cur.execute(
                    """INSERT INTO transactions
                       (user_id, type, amount, description, category, channel, reference, status)
                       VALUES (%s,'WITHDRAWAL',%s,'Cash Withdrawal','Withdrawal','ATM',%s,'completed')""",
                    (user["id"], amount, f"WDR{random.randint(100000,999999)}"),
                )
                conn.commit()
            flash(f"₹{amount:,.2f} withdrawn successfully!", "success")
        return redirect(url_for("withdraw"))

    user = get_user(session["user_id"])
    return render_template("withdraw.html", user=user)


@app.route("/transactions")
@login_required
def transactions():
    user = get_user(session["user_id"])
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, type, amount, description, counterparty, category,
                      channel, reference, status, timestamp
               FROM transactions WHERE user_id=%s ORDER BY timestamp DESC""",
            (user["id"],),
        )
        txns = cur.fetchall()
    return render_template("transactions.html", user=user, transactions=txns)


@app.route("/transfers", methods=["GET", "POST"])
@login_required
def transfers():
    user = get_user(session["user_id"])

    if request.method == "POST":
        transfer_type = request.form.get("transfer_type")
        cfg = get_config()
        ff = get_feature_flags()
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if transfer_type == "self":
                    direction = request.form.get("direction")
                    amount = float(request.form.get("amount", 0))
                    if amount <= 0:
                        flash("Enter a valid amount.", "error")
                    elif direction == "to_savings":
                        if amount > user["balance"]:
                            flash("Insufficient wallet balance.", "error")
                        else:
                            cur.execute(
                                "UPDATE users SET balance=balance-%s, savings_balance=savings_balance+%s WHERE id=%s",
                                (amount, amount, user["id"]),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'SELF_TRANSFER',%s,'Wallet → Savings','Transfer','Online',%s,'completed')""",
                                (user["id"], amount, f"SLF{random.randint(100000,999999)}"),
                            )
                            conn.commit()
                            flash(f"₹{amount:,.2f} moved to Savings.", "success")
                    elif direction == "to_wallet":
                        if amount > user["savings"]:
                            flash("Insufficient savings balance.", "error")
                        else:
                            cur.execute(
                                "UPDATE users SET balance=balance+%s, savings_balance=savings_balance-%s WHERE id=%s",
                                (amount, amount, user["id"]),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'SELF_TRANSFER',%s,'Savings → Wallet','Transfer','Online',%s,'completed')""",
                                (user["id"], amount, f"SLF{random.randint(100000,999999)}"),
                            )
                            conn.commit()
                            flash(f"₹{amount:,.2f} moved to Wallet.", "success")

                elif transfer_type == "bank":
                    recipient = request.form.get("recipient", "").strip()
                    amount = float(request.form.get("amount", 0))
                    if amount <= 0 or not recipient:
                        flash("Enter valid details.", "error")
                    elif amount > user["balance"]:
                        flash("Insufficient balance.", "error")
                    elif _is_high_value(amount, cfg, ff):
                        _create_approval(conn, user, amount,
                                         f"Bank transfer to {recipient}")
                        flash(f"High-value transfer (₹{amount:,.2f}) routed for admin approval.", "info")
                    else:
                        cur.execute("SELECT id FROM users WHERE name=%s", (recipient,))
                        rcpt = cur.fetchone()
                        if not rcpt:
                            flash("Recipient not found.", "error")
                        else:
                            cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                            cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, rcpt[0]))
                            ref = f"BNK{random.randint(100000,999999)}"
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'TRANSFER_OUT',%s,%s,'Transfer','Online',%s,'completed')""",
                                (user["id"], amount, f"Transfer to {recipient}", ref),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'TRANSFER_IN',%s,%s,'Transfer','Online',%s,'completed')""",
                                (rcpt[0], amount, f"Transfer from {user['name']}", ref),
                            )
                            cur.execute(
                                """INSERT INTO transfers
                                   (sender_id, receiver_info, amount, type, channel, reference, status)
                                   VALUES (%s,%s,%s,'Bank','Online',%s,'COMPLETED')""",
                                (user["id"], recipient, amount, ref),
                            )
                            conn.commit()
                            flash(f"₹{amount:,.2f} sent to {recipient}.", "success")

                elif transfer_type == "upi":
                    upi_id = request.form.get("upi_id", "").strip()
                    amount = float(request.form.get("amount", 0))
                    if amount <= 0 or not upi_id:
                        flash("Enter valid details.", "error")
                    elif amount > user["balance"]:
                        flash("Insufficient balance.", "error")
                    elif _is_high_value(amount, cfg, ff):
                        _create_approval(conn, user, amount,
                                         f"UPI to {upi_id}")
                        flash(f"High-value transfer (₹{amount:,.2f}) routed for admin approval.", "info")
                    else:
                        cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                        ref = f"UPI{random.randint(100000,999999)}"
                        cur.execute(
                            """INSERT INTO transactions
                               (user_id, type, amount, description, category, channel, reference, status)
                               VALUES (%s,'TRANSFER_OUT',%s,%s,'Transfer','UPI',%s,'completed')""",
                            (user["id"], amount, f"UPI to {upi_id}", ref),
                        )
                        cur.execute(
                            """INSERT INTO transfers
                               (sender_id, receiver_info, amount, type, channel, reference, status)
                               VALUES (%s,%s,%s,'UPI','UPI',%s,'COMPLETED')""",
                            (user["id"], upi_id, amount, ref),
                        )
                        conn.commit()
                        flash(f"₹{amount:,.2f} sent via UPI to {upi_id}.", "success")

                elif transfer_type == "international":
                    if not flag_enabled("intl_transfers", ff):
                        flash("International transfers are currently disabled.", "error")
                    else:
                        currency = request.form.get("currency", "USD")
                        foreign_amount = float(request.form.get("foreign_amount", 0))
                        rates = {"USD": 83.42, "EUR": 90.15, "GBP": 105.30}
                        rate = rates.get(currency, 83.42)
                        inr_amount = round(foreign_amount * rate, 2)
                        fee = float(cfg.get("transfer_fee_international", "500"))
                        total = inr_amount + fee
                        if foreign_amount <= 0:
                            flash("Enter a valid amount.", "error")
                        elif total > user["balance"]:
                            flash(f"Insufficient balance. Total: ₹{total:,.2f} (incl. ₹{fee:,.2f} fee).", "error")
                        elif _is_high_value(total, cfg, ff):
                            _create_approval(conn, user, total,
                                             f"SWIFT {currency} {foreign_amount:.2f} @{rate}")
                            flash(f"High-value transfer (₹{total:,.2f}) routed for admin approval.", "info")
                        else:
                            cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, user["id"]))
                            ref = f"SWF{random.randint(100000,999999)}"
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'TRANSFER_OUT',%s,%s,'Transfer','SWIFT',%s,'completed')""",
                                (user["id"], total, f"Intl {currency} {foreign_amount:.2f} @{rate}", ref),
                            )
                            cur.execute(
                                """INSERT INTO transfers
                                   (sender_id, receiver_info, amount, type, channel, reference, status)
                                   VALUES (%s,%s,%s,'International','SWIFT',%s,'COMPLETED')""",
                                (user["id"], f"{currency} {foreign_amount:.2f}", total, ref),
                            )
                            conn.commit()
                            flash(f"₹{inr_amount:,.2f} + ₹{fee:,.2f} fee sent internationally.", "success")

                elif transfer_type == "neft":
                    recipient = request.form.get("recipient", "").strip()
                    amount = float(request.form.get("amount", 0))
                    fee = float(cfg.get("transfer_fee_domestic", "5"))
                    total = amount + fee
                    if amount <= 0 or not recipient:
                        flash("Enter valid details.", "error")
                    elif total > user["balance"]:
                        flash(f"Insufficient balance. Total: ₹{total:,.2f} (incl. ₹{fee:,.2f} fee).", "error")
                    elif _is_high_value(total, cfg, ff):
                        _create_approval(conn, user, total,
                                         f"NEFT to {recipient}")
                        flash(f"High-value transfer (₹{total:,.2f}) routed for admin approval.", "info")
                    else:
                        cur.execute("SELECT id FROM users WHERE name=%s", (recipient,))
                        rcpt = cur.fetchone()
                        if not rcpt:
                            flash("Recipient not found.", "error")
                        else:
                            cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, user["id"]))
                            cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, rcpt[0]))
                            ref = f"NEFT{random.randint(100000,999999)}"
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'TRANSFER_OUT',%s,%s,'Transfer','NEFT',%s,'completed')""",
                                (user["id"], total, f"NEFT to {recipient}", ref),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'TRANSFER_IN',%s,%s,'Transfer','NEFT',%s,'completed')""",
                                (rcpt[0], amount, f"NEFT from {user['name']}", ref),
                            )
                            cur.execute(
                                """INSERT INTO transfers
                                   (sender_id, receiver_info, amount, type, channel, reference, status)
                                   VALUES (%s,%s,%s,'NEFT','NEFT',%s,'COMPLETED')""",
                                (user["id"], recipient, total, ref),
                            )
                            conn.commit()
                            flash(f"₹{amount:,.2f} + ₹{fee:,.2f} fee sent via NEFT to {recipient}.", "success")

                elif transfer_type == "issue_cheque":
                    if not flag_enabled("cheque_issuance", ff):
                        flash("Cheque issuance is currently disabled.", "error")
                    else:
                        receiver = request.form.get("receiver", "").strip()
                        amount = float(request.form.get("amount", 0))
                        if amount <= 0 or not receiver:
                            flash("Enter valid details.", "error")
                        elif amount > user["balance"]:
                            flash("Insufficient balance.", "error")
                        else:
                            cur.execute(
                                "INSERT INTO cheques (issuer_id, receiver_name, amount) VALUES (%s,%s,%s)",
                                (user["id"], receiver, amount),
                            )
                            conn.commit()
                            flash(f"Cheque for ₹{amount:,.2f} issued to {receiver}.", "success")

                elif transfer_type == "approve_cheque":
                    cheque_id = int(request.form.get("cheque_id", 0))
                    cur.execute(
                        "SELECT issuer_id, amount FROM cheques WHERE id=%s AND receiver_name=%s AND status='PENDING'",
                        (cheque_id, user["name"]),
                    )
                    ch = cur.fetchone()
                    if not ch:
                        flash("Invalid cheque.", "error")
                    else:
                        issuer_id, amount = ch
                        cur.execute("SELECT balance FROM users WHERE id=%s", (issuer_id,))
                        ib = float(cur.fetchone()[0])
                        if ib < amount:
                            flash("Issuer has insufficient funds.", "error")
                        else:
                            cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, issuer_id))
                            cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user["id"]))
                            cur.execute("UPDATE cheques SET status='CLEARED' WHERE id=%s", (cheque_id,))
                            ref = f"CHQ{random.randint(100000,999999)}"
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'CHEQUE_OUT',%s,'Cheque cleared','Transfer','Cheque',%s,'completed')""",
                                (issuer_id, amount, ref),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'CHEQUE_IN',%s,'Cheque received','Transfer','Cheque',%s,'completed')""",
                                (user["id"], amount, ref),
                            )
                            conn.commit()
                            flash(f"Cheque for ₹{amount:,.2f} approved and collected!", "success")

            except Exception as e:
                flash(f"Error: {e}", "error")

        return redirect(url_for("transfers"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT receiver_info, amount, type, timestamp
               FROM transfers WHERE sender_id=%s ORDER BY timestamp DESC LIMIT 10""",
            (user["id"],),
        )
        recent_transfers = cur.fetchall()

        cur.execute(
            """SELECT id, issuer_id, amount, status, issued_at
               FROM cheques WHERE receiver_name=%s AND status='PENDING'""",
            (user["name"],),
        )
        pending_cheques = cur.fetchall()

    user = get_user(session["user_id"])
    return render_template(
        "transfers.html", user=user,
        recent_transfers=recent_transfers,
        pending_cheques=pending_cheques,
    )


@app.route("/loans", methods=["GET", "POST"])
@login_required
def loans():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if action == "apply":
                    if not flag_enabled("loans_self_serve"):
                        flash("Self-serve loans are currently disabled. Contact your RM.", "error")
                    else:
                        principal = float(request.form.get("principal", 0))
                        if principal <= 0:
                            flash("Enter a valid loan amount.", "error")
                        else:
                            rate = 5.0
                            total = round(principal * (1 + rate / 100), 2)
                            emi = round(total / 12, 2)
                            cur.execute(
                                """INSERT INTO loans
                                   (user_id, loan_type, principal, interest_rate, term_months,
                                    emi, total_owed, outstanding, status, next_due_date)
                                   VALUES (%s,'Personal',%s,%s,12,%s,%s,%s,'ACTIVE',%s)""",
                                (user["id"], principal, rate, emi, total, total,
                                 (datetime.now() + timedelta(days=30)).date()),
                            )
                            cur.execute(
                                "UPDATE users SET balance=balance+%s WHERE id=%s",
                                (principal, user["id"]),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'LOAN_DISBURSEMENT',%s,'Loan disbursement','Loan','Online',%s,'completed')""",
                                (user["id"], principal, f"LN{random.randint(100000,999999)}"),
                            )
                            conn.commit()
                            flash(f"Loan of ₹{principal:,.2f} approved! Funds credited.", "success")

                elif action == "repay":
                    loan_id = int(request.form.get("loan_id", 0))
                    amount = float(request.form.get("amount", 0))
                    if amount <= 0:
                        flash("Enter a valid amount.", "error")
                    elif amount > user["balance"]:
                        flash("Insufficient balance.", "error")
                    else:
                        cur.execute(
                            "SELECT outstanding FROM loans WHERE id=%s AND user_id=%s AND status='ACTIVE'",
                            (loan_id, user["id"]),
                        )
                        row = cur.fetchone()
                        if not row:
                            flash("Loan not found.", "error")
                        else:
                            outstanding = float(row[0])
                            pay = min(amount, outstanding)
                            new_outstanding = outstanding - pay
                            new_status = "PAID" if new_outstanding <= 0 else "ACTIVE"
                            cur.execute(
                                "UPDATE loans SET amount_paid=amount_paid+%s, outstanding=%s, status=%s WHERE id=%s",
                                (pay, max(0, new_outstanding), new_status, loan_id),
                            )
                            cur.execute(
                                "UPDATE users SET balance=balance-%s WHERE id=%s",
                                (pay, user["id"]),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'LOAN_PAYMENT',%s,'Loan repayment','Loan','Online',%s,'completed')""",
                                (user["id"], pay, f"LNPAY{random.randint(100000,999999)}"),
                            )
                            conn.commit()
                            if new_status == "PAID":
                                flash(f"Loan fully repaid! ₹{pay:,.2f} paid.", "success")
                            else:
                                flash(f"₹{pay:,.2f} paid. Remaining: ₹{new_outstanding:,.2f}", "success")

            except Exception as e:
                flash(f"Error: {e}", "error")

        return redirect(url_for("loans"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, loan_type, principal, interest_rate, term_months, emi,
                      total_owed, amount_paid, outstanding, status, next_due_date, timestamp
               FROM loans WHERE user_id=%s ORDER BY timestamp DESC""",
            (user["id"],),
        )
        all_loans = cur.fetchall()

    return render_template("loans.html", user=user, loans=all_loans)


@app.route("/bills", methods=["GET", "POST"])
@login_required
def bills():
    user = get_user(session["user_id"])

    if request.method == "POST":
        bill_id = int(request.form.get("bill_id", 0))
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT amount FROM bills WHERE id=%s AND user_id=%s AND status IN ('PENDING','OVERDUE')",
                (bill_id, user["id"]),
            )
            row = cur.fetchone()
            if not row:
                flash("Bill not found.", "error")
            elif float(row[0]) > user["balance"]:
                flash("Insufficient balance.", "error")
            else:
                amount = float(row[0])
                cur.execute("UPDATE bills SET status='PAID' WHERE id=%s", (bill_id,))
                cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                cur.execute(
                    """INSERT INTO transactions
                       (user_id, type, amount, description, category, channel, reference, status)
                       VALUES (%s,'BILL_PAYMENT',%s,'Bill payment','Bills','Online',%s,'completed')""",
                    (user["id"], amount, f"BILL{random.randint(100000,999999)}"),
                )
                conn.commit()
                flash(f"₹{amount:,.2f} bill paid successfully!", "success")

        return redirect(url_for("bills"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, biller, category, amount, due_date, status
               FROM bills WHERE user_id=%s ORDER BY due_date ASC""",
            (user["id"],),
        )
        all_bills = cur.fetchall()

    return render_template("bills.html", user=user, bills=all_bills)


@app.route("/cards", methods=["GET", "POST"])
@login_required
def cards():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if action == "issue":
                    card_type = request.form.get("card_type", "Debit")
                    brand = request.form.get("brand", "Visa")
                    last4 = str(random.randint(1000, 9999))
                    card_num = f"{last4} XXXX XXXX {last4}"
                    limit_amt = 100000 if card_type == "Credit" else 0
                    exp = (datetime.now() + timedelta(days=730)).date()
                    cur.execute(
                        """INSERT INTO cards
                           (user_id, card_number, brand, card_type, last4, status,
                            card_limit, used, expiry_date)
                           VALUES (%s,%s,%s,%s,%s,'ACTIVE',%s,0,%s)""",
                        (user["id"], card_num, brand, card_type, last4, limit_amt, exp),
                    )
                    conn.commit()
                    flash(f"New {brand} {card_type} card issued!", "success")

                elif action == "toggle":
                    card_id = int(request.form.get("card_id", 0))
                    cur.execute(
                        "SELECT status FROM cards WHERE id=%s AND user_id=%s",
                        (card_id, user["id"]),
                    )
                    row = cur.fetchone()
                    if row:
                        new_status = "BLOCKED" if row[0] == "ACTIVE" else "ACTIVE"
                        cur.execute("UPDATE cards SET status=%s WHERE id=%s", (new_status, card_id))
                        conn.commit()
                        flash(f"Card {'blocked' if new_status == 'BLOCKED' else 'activated'}.", "success")
            except Exception as e:
                flash(f"Error: {e}", "error")

        return redirect(url_for("cards"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, card_number, brand, card_type, last4, status,
                      card_limit, used, expiry_date
               FROM cards WHERE user_id=%s ORDER BY created_at DESC""",
            (user["id"],),
        )
        all_cards = cur.fetchall()

    return render_template("cards.html", user=user, cards=all_cards)


@app.route("/investments", methods=["GET", "POST"])
@login_required
@feature_guard("investments")
def investments():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if action == "invest":
                    inv_type = request.form.get("inv_type")
                    amount = float(request.form.get("amount", 0))
                    rates = {"FD": 0.065, "BONDS": 0.07, "MF": 0.12}
                    if inv_type not in rates or amount <= 0:
                        flash("Invalid investment.", "error")
                    elif amount > user["balance"]:
                        flash("Insufficient balance.", "error")
                    else:
                        ret = round(amount * rates[inv_type], 2)
                        cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                        cur.execute(
                            """INSERT INTO investments
                               (user_id, symbol, inv_name, inv_type, category,
                                shares, avg_cost, price, amount, returns, change_pct)
                               VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s,0)""",
                            (user["id"], inv_type, f"{inv_type} Investment",
                             inv_type, "FD" if inv_type == "FD" else "Bond" if inv_type == "BONDS" else "MF",
                             amount, amount, amount, ret),
                        )
                        cur.execute(
                            """INSERT INTO transactions
                               (user_id, type, amount, description, category, channel, reference, status)
                               VALUES (%s,'INVESTMENT',%s,%s,'Investments','Online',%s,'completed')""",
                            (user["id"], amount, f"Invested in {inv_type}",
                             f"INV{random.randint(100000,999999)}"),
                        )
                        add_txn(conn, user["id"], "INVESTMENT_PURCHASE", amount, f"{inv_type} investment", "investments")
                        conn.commit()
                        flash(f"₹{amount:,.2f} invested in {inv_type}! Expected return: ₹{ret:,.2f}", "success")

                elif action == "stock":
                    symbol = request.form.get("stock")
                    qty = int(request.form.get("qty", 0))
                    cur.execute("SELECT price FROM stocks WHERE symbol=%s", (symbol,))
                    srow = cur.fetchone()
                    if not srow or qty <= 0:
                        flash("Invalid stock or quantity.", "error")
                    else:
                        price = float(srow[0])
                        total = price * qty
                        if total > user["balance"]:
                            flash("Insufficient balance.", "error")
                        else:
                            cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, user["id"]))
                            cur.execute(
                                """INSERT INTO investments
                                   (user_id, symbol, inv_name, inv_type, category,
                                    shares, avg_cost, price, amount, returns, change_pct)
                                   VALUES (%s,%s,%s,'Stock','Equity',%s,%s,%s,%s,0,0)""",
                                (user["id"], symbol, symbol, qty, price, price, total),
                            )
                            cur.execute(
                                """INSERT INTO transactions
                                   (user_id, type, amount, description, category, channel, reference, status)
                                   VALUES (%s,'INVESTMENT',%s,%s,'Investments','Online',%s,'completed')""",
                                (user["id"], total, f"Bought {qty}x {symbol}",
                                 f"STK{random.randint(100000,999999)}"),
                            )
                            conn.commit()
                            flash(f"Bought {qty}x {symbol} for ₹{total:,.2f}!", "success")

            except Exception as e:
                flash(f"Error: {e}", "error")

        return redirect(url_for("investments"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, symbol, inv_name, inv_type, category, shares,
                      avg_cost, price, amount, returns, change_pct, maturity
               FROM investments WHERE user_id=%s ORDER BY timestamp DESC""",
            (user["id"],),
        )
        all_investments = cur.fetchall()

        cur.execute("SELECT symbol, name, price, change_pct FROM stocks ORDER BY symbol")
        all_stocks = cur.fetchall()

    return render_template("investments.html", user=user,
                           investments=all_investments, stocks=all_stocks)


@app.route("/pfm", methods=["GET", "POST"])
@login_required
def pfm():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if action == "add_goal":
                    name = request.form.get("goal_name", "").strip()
                    target = float(request.form.get("target", 0))
                    deadline = request.form.get("deadline")
                    if name and target > 0 and deadline:
                        cur.execute(
                            """INSERT INTO goals (user_id, goal_name, target_amount, deadline)
                               VALUES (%s,%s,%s,%s)""",
                            (user["id"], name, target, deadline),
                        )
                        conn.commit()
                        flash(f"Goal '{name}' added!", "success")

                elif action == "save_goal":
                    goal_id = int(request.form.get("goal_id", 0))
                    amount = float(request.form.get("amount", 0))
                    if amount > 0 and amount <= user["balance"]:
                        cur.execute(
                            "UPDATE goals SET saved_amount=saved_amount+%s WHERE id=%s AND user_id=%s",
                            (amount, goal_id, user["id"]),
                        )
                        cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user["id"]))
                        cur.execute(
                            """INSERT INTO transactions
                               (user_id, type, amount, description, category, channel, reference, status)
                               VALUES (%s,'GOAL_SAVING',%s,'Goal saving','Savings','Online',%s,'completed')""",
                            (user["id"], amount, f"GOAL{random.randint(100000,999999)}"),
                        )
                        conn.commit()
                        flash(f"₹{amount:,.2f} saved toward goal!", "success")
                    else:
                        flash("Invalid amount or insufficient balance.", "error")

                elif action == "update_budget":
                    budget_id = int(request.form.get("budget_id", 0))
                    new_limit = float(request.form.get("monthly_limit", 0))
                    if new_limit > 0:
                        cur.execute(
                            "UPDATE budgets SET monthly_limit=%s WHERE id=%s AND user_id=%s",
                            (new_limit, budget_id, user["id"]),
                        )
                        conn.commit()
                        flash("Budget updated!", "success")

            except Exception as e:
                flash(f"Error: {e}", "error")

        return redirect(url_for("pfm"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, category, monthly_limit, spent FROM budgets WHERE user_id=%s ORDER BY category",
            (user["id"],),
        )
        budgets = cur.fetchall()

        cur.execute(
            """SELECT id, goal_name, target_amount, saved_amount, deadline, status
               FROM goals WHERE user_id=%s ORDER BY deadline""",
            (user["id"],),
        )
        goals = cur.fetchall()

    return render_template("pfm.html", user=user, budgets=budgets, goals=goals)


@app.route("/profile")
@login_required
def profile():
    user = get_user(session["user_id"])
    return render_template("profile.html", user=user)


# ── Admin Routes ──────────────────────────────────────────────────────────────

@app.route("/admin/")
@admin_required
def admin_dashboard():
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'")
        pending_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM approvals WHERE status='pending' AND risk='high'")
        high_risk = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE status='active'")
        active_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE status='frozen'")
        frozen_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM transactions WHERE status='flagged'")
        flagged_txns = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(balance + savings_balance), 0) FROM users")
        total_aum = float(cur.fetchone()[0])

        cur.execute(
            """SELECT kind, detail, risk, amount, status, submitted_by, submitted_at
               FROM approvals WHERE status='pending'
               ORDER BY submitted_at DESC LIMIT 5""",
        )
        pending_approvals = cur.fetchall()

        cur.execute(
            "SELECT ts, actor, action, target, meta FROM audit_log ORDER BY ts DESC LIMIT 8",
        )
        recent_audit = cur.fetchall()

    return render_template(
        "admin/dashboard.html",
        pending_count=pending_count, high_risk=high_risk,
        active_users=active_users, frozen_users=frozen_users,
        flagged_txns=flagged_txns, total_aum=total_aum,
        pending_approvals=pending_approvals, recent_audit=recent_audit,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, email, role, tier, status, balance,
                      savings_balance, account_number, ifsc_code, branch, created_at
               FROM users ORDER BY created_at DESC""",
        )
        users = cur.fetchall()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:uid>/toggle-freeze", methods=["POST"])
@admin_required
def admin_toggle_freeze(uid):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, status FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        if row:
            new_status = "frozen" if row[1] == "active" else "active"
            cur.execute("UPDATE users SET status=%s WHERE id=%s", (new_status, uid))
            log_audit(conn, session.get("user_name", "admin"), "user.toggle-freeze",
                      row[0], f"{row[1]} → {new_status}")
            conn.commit()
            flash(f"{row[0]} account {'frozen' if new_status == 'frozen' else 'unfrozen'}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/approvals")
@admin_required
def admin_approvals():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, kind, submitted_by, submitted_at, amount, detail, risk, status
               FROM approvals ORDER BY submitted_at DESC""",
        )
        approvals = cur.fetchall()
    return render_template("admin/approvals.html", approvals=approvals)


@app.route("/admin/approvals/<int:aid>/approve", methods=["POST"])
@admin_required
def admin_approve(aid):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE approvals SET status='approved' WHERE id=%s", (aid,))
        log_audit(conn, session.get("user_name", "admin"), "approval.approve",
                  str(aid), None)
        conn.commit()
        flash("Approval granted.", "success")
    return redirect(url_for("admin_approvals"))


@app.route("/admin/approvals/<int:aid>/reject", methods=["POST"])
@admin_required
def admin_reject(aid):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE approvals SET status='rejected' WHERE id=%s", (aid,))
        log_audit(conn, session.get("user_name", "admin"), "approval.reject",
                  str(aid), None)
        conn.commit()
        flash("Approval rejected.", "success")
    return redirect(url_for("admin_approvals"))


@app.route("/admin/configuration", methods=["GET", "POST"])
@admin_required
def admin_configuration():
    if request.method == "POST":
        key = request.form.get("key")
        value = request.form.get("value")
        if key and value is not None:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO config (key, value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s",
                    (key, value, value),
                )
                log_audit(conn, session.get("user_name", "admin"),
                          "config.update", key, value)
                conn.commit()
                flash(f"Config '{key}' updated.", "success")
        return redirect(url_for("admin_configuration"))

    cfg = get_config()
    rows = [
        ("transfer_limit_daily", "Daily Transfer Limit", "₹", "Max transfer per user per day"),
        ("transfer_fee_domestic", "Domestic Transfer Fee", "₹", "Per NEFT / IMPS transfer"),
        ("transfer_fee_international", "International Transfer Fee", "₹", "Per SWIFT / wire transfer"),
        ("high_value_threshold", "High-Value Threshold", "₹", "Routes transfer to approval queue"),
        ("overdraft_fee", "Overdraft Fee", "₹", "Charged on negative balance"),
        ("savings_rate", "Savings APY", "%", "Standard savings account rate"),
    ]
    return render_template("admin/configuration.html", config=cfg, rows=rows)


@app.route("/admin/fx")
@admin_required
def admin_fx():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pair, rate, updated_at FROM fx_rates ORDER BY pair")
        fx_rates = cur.fetchall()
    return render_template("admin/fx.html", fx_rates=fx_rates)


@app.route("/admin/stocks")
@admin_required
def admin_stocks():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT symbol, name, price, change_pct FROM stocks ORDER BY symbol")
        stocks = cur.fetchall()
    return render_template("admin/stocks.html", stocks=stocks)


@app.route("/admin/flags", methods=["GET"])
@admin_required
def admin_flags():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, label, description, enabled FROM feature_flags ORDER BY key")
        flags = cur.fetchall()
    return render_template("admin/flags.html", flags=flags)


@app.route("/admin/flags/<key>/toggle", methods=["POST"])
@admin_required
def admin_flag_toggle(key):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT enabled FROM feature_flags WHERE key=%s", (key,))
        row = cur.fetchone()
        if row:
            new_val = not row[0]
            cur.execute("UPDATE feature_flags SET enabled=%s WHERE key=%s", (new_val, key))
            log_audit(conn, session.get("user_name", "admin"),
                      "flag.toggle", key, str(new_val))
            conn.commit()
            flash(f"Flag '{key}' {'enabled' if new_val else 'disabled'}.", "success")
    return redirect(url_for("admin_flags"))


@app.route("/admin/audit")
@admin_required
def admin_audit():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ts, actor, action, target, meta FROM audit_log ORDER BY ts DESC LIMIT 100",
        )
        audit = cur.fetchall()
    return render_template("admin/audit.html", audit=audit)


@app.route("/admin/seed", methods=["GET", "POST"])
@admin_required
def admin_seed():
    if request.method == "POST":
        reset_demo_data()
        with get_db() as conn:
            log_audit(conn, session.get("user_name", "admin"),
                      "system.reseed", "all", None)
            conn.commit()
        flash("Demo data has been reset!", "success")
        return redirect(url_for("admin_seed"))
    return render_template("admin/seed.html")


# ── API (kept for compatibility) ──────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    name = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not name or not password:
        return jsonify({"error": "Username and password required."}), 400
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, password, role FROM users WHERE name=%s", (name,))
        row = cur.fetchone()
    if not row or not check_password_hash(row[2], password):
        return jsonify({"error": "Invalid credentials."}), 401
    session["user_id"] = row[0]
    session["user_name"] = row[1]
    session["role"] = row[3]
    return jsonify({"ok": True, "role": row[3], "name": row[1]})


# ── Startup ───────────────────────────────────────────────────────────────────

db_init()
seed_demo_data()

if __name__ == "__main__":
    app.run(debug=True)
