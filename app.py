import os
import uuid
import random
import secrets
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

import bcrypt
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from flask_wtf.csrf import CSRFProtect

from demo_personas import public_personas

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
csrf = CSRFProtect(app)

db_url = (os.getenv("DATABASE_URL") or "").strip()


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)


def money(v):
    """Coerce any numeric to Decimal with 2 dp."""
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ref():
    return str(uuid.uuid4()).replace("-", "").upper()[:12]


def get_config(key, default=None):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE key=%s", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default


def feature_enabled(key):
    v = get_config(key, "true")
    return str(v).lower() in ("1", "true", "yes", "on")


def get_fx_rate(currency):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT rate FROM fx_rates WHERE base=%s AND quote='INR'", (currency,))
        row = cur.fetchone()
        conn.close()
        return money(row["rate"]) if row else None
    except Exception:
        return None


def get_stock_price(symbol):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT price FROM stocks WHERE symbol=%s", (symbol,))
        row = cur.fetchone()
        conn.close()
        return money(row["price"]) if row else None
    except Exception:
        return None


# ── Schema ────────────────────────────────────────────────────────────────────

def db_init():
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT DEFAULT '',
            email TEXT,
            phone TEXT,
            dob DATE,
            role TEXT DEFAULT 'USER',
            status TEXT DEFAULT 'ACTIVE',
            kyc_status TEXT DEFAULT 'VERIFIED',
            frozen_at TIMESTAMP,
            frozen_reason TEXT,
            password_hash TEXT NOT NULL,
            balance NUMERIC DEFAULT 0,
            savings_balance NUMERIC DEFAULT 0,
            account_number TEXT UNIQUE,
            ifsc TEXT DEFAULT 'PRPB0000001',
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            amount NUMERIC NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            channel TEXT DEFAULT '',
            reference_id TEXT UNIQUE,
            counterparty_id INTEGER REFERENCES users(id),
            status TEXT DEFAULT 'SUCCESS',
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            principal NUMERIC NOT NULL,
            interest_rate NUMERIC DEFAULT 10.5,
            tenure_months INTEGER DEFAULT 12,
            emi NUMERIC DEFAULT 0,
            total_owed NUMERIC NOT NULL,
            amount_paid NUMERIC DEFAULT 0,
            purpose TEXT DEFAULT '',
            status TEXT DEFAULT 'PENDING_APPROVAL',
            approved_by INTEGER REFERENCES users(id),
            approved_at TIMESTAMP,
            next_due_date DATE,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            bill_type VARCHAR(50),
            biller_name TEXT DEFAULT '',
            consumer_id TEXT DEFAULT '',
            amount NUMERIC,
            due_date DATE,
            status VARCHAR(20) DEFAULT 'PENDING',
            paid_at TIMESTAMP,
            payment_txn_id INTEGER REFERENCES transactions(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            card_number TEXT UNIQUE,
            holder_name TEXT DEFAULT '',
            card_type TEXT DEFAULT 'DEBIT',
            network TEXT DEFAULT 'VISA',
            status VARCHAR(20) DEFAULT 'ACTIVE',
            expiry_date DATE,
            daily_limit NUMERIC DEFAULT 50000,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS investments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(30),
            amount NUMERIC,
            quantity NUMERIC DEFAULT 0,
            unit_price_at_buy NUMERIC DEFAULT 0,
            returns NUMERIC DEFAULT 0,
            current_value NUMERIC DEFAULT 0,
            maturity_date DATE,
            redeemed_at TIMESTAMP,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            goal_name TEXT,
            target_amount NUMERIC,
            saved_amount NUMERIC DEFAULT 0,
            deadline DATE,
            status VARCHAR(20) DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            category TEXT,
            monthly_limit NUMERIC,
            spent NUMERIC DEFAULT 0,
            period_start DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER REFERENCES users(id),
            receiver_info TEXT,
            amount NUMERIC,
            fee NUMERIC DEFAULT 0,
            currency TEXT DEFAULT 'INR',
            fx_rate NUMERIC DEFAULT 1,
            type VARCHAR(30),
            status VARCHAR(20) DEFAULT 'COMPLETED',
            reference_id TEXT UNIQUE,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cheques (
            id SERIAL PRIMARY KEY,
            issuer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_name TEXT,
            receiver_id INTEGER REFERENCES users(id),
            cheque_number TEXT UNIQUE,
            amount NUMERIC,
            funds_locked BOOLEAN DEFAULT TRUE,
            status VARCHAR(20) DEFAULT 'PENDING',
            issued_at TIMESTAMP DEFAULT NOW(),
            cleared_at TIMESTAMP,
            bounced_reason TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            description TEXT DEFAULT '',
            updated_by INTEGER REFERENCES users(id),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fx_rates (
            id SERIAL PRIMARY KEY,
            base TEXT NOT NULL,
            quote TEXT NOT NULL DEFAULT 'INR',
            rate NUMERIC NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(base, quote)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price NUMERIC NOT NULL,
            day_change NUMERIC DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS approval_queue (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            payload_json TEXT,
            requester_id INTEGER REFERENCES users(id),
            amount NUMERIC DEFAULT 0,
            status TEXT DEFAULT 'PENDING',
            reviewed_by INTEGER REFERENCES users(id),
            reviewed_at TIMESTAMP,
            reason TEXT,
            reference_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feature_flags (
            key TEXT PRIMARY KEY,
            enabled BOOLEAN DEFAULT TRUE,
            description TEXT DEFAULT ''
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            before_json TEXT,
            after_json TEXT,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')

    # Insert default config if empty
    cur.execute("SELECT COUNT(*) FROM config")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("loan_interest_rate", "10.5", "rates", "Annual loan interest rate (%)"),
            ("fd_rate", "6.5", "rates", "Fixed deposit annual return (%)"),
            ("bonds_rate", "7.5", "rates", "Bond annual return (%)"),
            ("mf_rate", "11.0", "rates", "Mutual fund annual return (%)"),
            ("neft_fee", "5.00", "fees", "NEFT flat fee (INR)"),
            ("intl_flat_fee", "50.00", "fees", "International transfer flat fee (INR)"),
            ("intl_spread_pct", "1.0", "fees", "International transfer spread (%)"),
            ("daily_withdraw_limit", "50000", "limits", "Max daily withdrawal (INR)"),
            ("high_value_threshold", "500000", "limits", "Amount above which transfer needs admin approval"),
            ("bill_due_days", "7", "windows", "Days until bill due date from creation"),
            ("require_loan_approval", "true", "features", "Loans need admin approval before disbursal"),
            ("demo_mode", "true", "features", "Show demo-credentials panel on login"),
        ]
        cur.executemany(
            "INSERT INTO config (key,value,category,description) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            defaults,
        )

    # Insert default FX rates if empty
    cur.execute("SELECT COUNT(*) FROM fx_rates")
    if cur.fetchone()[0] == 0:
        fx = [("USD", "INR", 83.45), ("EUR", "INR", 90.12), ("GBP", "INR", 105.60), ("AED", "INR", 22.70)]
        cur.executemany(
            "INSERT INTO fx_rates (base,quote,rate) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            fx,
        )

    # Insert default stocks if empty
    cur.execute("SELECT COUNT(*) FROM stocks")
    if cur.fetchone()[0] == 0:
        stx = [
            ("TechCorp", "TechCorp Ltd", 102.40),
            ("GreenEnergy", "GreenEnergy Ltd", 198.75),
            ("FinBank", "FinBank Ltd", 154.10),
            ("InfraBuild", "InfraBuild Ltd", 76.20),
        ]
        cur.executemany(
            "INSERT INTO stocks (symbol,name,price) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            stx,
        )

    # Insert default feature flags if empty
    cur.execute("SELECT COUNT(*) FROM feature_flags")
    if cur.fetchone()[0] == 0:
        flags = [
            ("enable_international_transfers", True, "Allow international transfers"),
            ("enable_cheques", True, "Allow cheque issuance and approval"),
            ("enable_loans", True, "Allow loan applications"),
            ("enable_stocks", True, "Allow stock purchases"),
            ("enable_neft", True, "Allow NEFT transfers"),
            ("enable_bills", True, "Allow bill management"),
            ("enable_investments", True, "Allow FD/Bonds/MF investments"),
        ]
        cur.executemany(
            "INSERT INTO feature_flags (key,enabled,description) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            flags,
        )

    conn.commit()
    conn.close()


db_init()


# ── User helpers ──────────────────────────────────────────────────────────────

def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, full_name, balance, savings_balance, role, status, account_number FROM users WHERE id=%s",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "name": row["username"],
            "full_name": row["full_name"] or row["username"],
            "balance": money(row["balance"]),
            "savings": money(row["savings_balance"]),
            "role": row["role"],
            "status": row["status"],
            "account_number": row["account_number"] or "N/A",
        }
    return None


def atomic_debit(conn, user_id, amount):
    """Debit atomically. Returns True on success, False if insufficient funds."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance=balance-%s WHERE id=%s AND balance>=%s RETURNING id",
        (amount, user_id, amount),
    )
    return cur.fetchone() is not None


def atomic_credit(conn, user_id, amount):
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user_id))


def add_txn(conn, user_id, txn_type, amount, description="", category="", channel="", counterparty_id=None):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO transactions (user_id, type, amount, description, category, channel, reference_id, counterparty_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (user_id, txn_type, amount, description, category, channel, ref(), counterparty_id),
    )


def update_budget(conn, user_id, category, amount):
    """Increment spent on matching budget for user."""
    if not category:
        return
    cur = conn.cursor()
    cur.execute(
        "UPDATE budgets SET spent=spent+%s WHERE user_id=%s AND LOWER(category)=LOWER(%s)",
        (amount, user_id, category),
    )


def audit(conn, admin_id, action, target_type=None, target_id=None, before=None, after=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (admin_id, action, target_type, target_id, before_json, after_json) VALUES (%s,%s,%s,%s,%s,%s)",
        (admin_id, action, target_type, target_id, before, after),
    )


# ── Decorators ────────────────────────────────────────────────────────────────

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
        user = get_user(session["user_id"])
        if not user or user["role"] != "ADMIN":
            flash("Access denied.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def feature_required(flag_key):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not feature_enabled(flag_key):
                flash("This feature is currently disabled.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    demo_on = get_config("demo_mode", "true").lower() in ("1", "true", "yes")
    personas = public_personas() if demo_on else []

    if request.method == "POST":
        username = (request.form.get("name") or "").strip()
        pw = (request.form.get("password") or "").strip()
        if not username or not pw:
            flash("Please fill in all fields.", "error")
            return render_template("login.html", personas=personas)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, role, status FROM users WHERE username=%s",
            (username,),
        )
        row = cur.fetchone()
        conn.close()

        if row and row["status"] == "FROZEN":
            flash("Your account has been frozen. Contact support.", "error")
            return render_template("login.html", personas=personas)

        if row and bcrypt.checkpw(pw.encode(), row["password_hash"].encode()):
            session["user_id"] = row["id"]
            session["user_name"] = row["username"]
            session["user_role"] = row["role"]
            return redirect(url_for("admin_dashboard") if row["role"] == "ADMIN" else url_for("dashboard"))

        flash("Invalid credentials.", "error")
    return render_template("login.html", personas=personas)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("name") or "").strip()
        pw = (request.form.get("password") or "").strip()
        full_name = (request.form.get("full_name") or username).strip()
        email = (request.form.get("email") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None

        if not username or not pw:
            flash("Username and password are required.", "error")
            return render_template("register.html")
        if len(pw) < 4:
            flash("Password must be at least 4 characters.", "error")
            return render_template("register.html")

        pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        acct_no = "PRPB" + str(random.randint(10000000, 99999999))

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO users (username, full_name, email, phone, password_hash, account_number)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (username, full_name, email, phone, pw_hash, acct_no),
            )
            conn.commit()
            conn.close()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            flash("Username or email already taken.", "error")
        except Exception:
            logger.exception("Registration error")
            flash("Registration failed. Please try again.", "error")
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_user(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT type, amount, timestamp, description FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 6",
        (user["id"],),
    )
    recent = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM loans WHERE user_id=%s AND status='ACTIVE'", (user["id"],))
    active_loans = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bills WHERE user_id=%s AND status='PENDING'", (user["id"],))
    pending_bills = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bills WHERE user_id=%s AND status='OVERDUE'", (user["id"],))
    overdue_bills = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(current_value),0) FROM investments WHERE user_id=%s AND redeemed_at IS NULL", (user["id"],))
    total_invested = money(cur.fetchone()[0])
    cur.execute(
        "SELECT COALESCE(SUM(total_owed - amount_paid), 0) FROM loans WHERE user_id=%s AND status='ACTIVE'",
        (user["id"],),
    )
    loan_liability = money(cur.fetchone()[0])
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM bills WHERE user_id=%s AND status IN ('PENDING','OVERDUE')",
        (user["id"],),
    )
    bill_liability = money(cur.fetchone()[0])
    cur.execute(
        "SELECT COUNT(*) FROM cheques WHERE receiver_name=%s AND status='PENDING'",
        (user["name"],),
    )
    pending_cheques = cur.fetchone()[0]
    conn.close()

    net_worth = user["balance"] + user["savings"] + total_invested - loan_liability - bill_liability

    return render_template(
        "dashboard.html",
        user=user,
        recent=recent,
        active_loans=active_loans,
        pending_bills=pending_bills,
        overdue_bills=overdue_bills,
        total_invested=total_invested,
        loan_liability=loan_liability,
        net_worth=net_worth,
        pending_cheques=pending_cheques,
    )


# ── Deposit ───────────────────────────────────────────────────────────────────

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    user = get_user(session["user_id"])
    if request.method == "POST":
        try:
            amount = money(request.form.get("amount") or 0)
            if amount <= 0:
                flash("Enter a positive amount.", "error")
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user["id"]))
                add_txn(conn, user["id"], "DEPOSIT", amount, "Cash deposit", "income", "online")
                conn.commit()
                conn.close()
                flash(f"₹{amount:,} deposited successfully.", "success")
                return redirect(url_for("dashboard"))
        except Exception:
            logger.exception("Deposit error")
            flash("Invalid input.", "error")
    return render_template("deposit.html", user=user)


# ── Withdraw ──────────────────────────────────────────────────────────────────

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    user = get_user(session["user_id"])
    if request.method == "POST":
        try:
            amount = money(request.form.get("amount") or 0)
            if amount <= 0:
                flash("Enter a positive amount.", "error")
            else:
                conn = get_db()
                success = atomic_debit(conn, user["id"], amount)
                if success:
                    add_txn(conn, user["id"], "WITHDRAWAL", amount, "Cash withdrawal", "expense", "online")
                    conn.commit()
                    flash(f"₹{amount:,} withdrawn successfully.", "success")
                    conn.close()
                    return redirect(url_for("dashboard"))
                else:
                    conn.close()
                    flash("Insufficient balance.", "error")
        except Exception:
            logger.exception("Withdraw error")
            flash("Invalid input.", "error")
    return render_template("withdraw.html", user=user)


# ── Transactions ──────────────────────────────────────────────────────────────

@app.route("/transactions")
@login_required
def transactions():
    user = get_user(session["user_id"])
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id=%s", (user["id"],)
    )
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT type, amount, timestamp, description, reference_id, channel FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s OFFSET %s",
        (user["id"], per_page, offset),
    )
    history = cur.fetchall()
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("transactions.html", user=user, history=history, page=page, total_pages=total_pages)


# ── Loans ─────────────────────────────────────────────────────────────────────

@app.route("/loans", methods=["GET", "POST"])
@login_required
@feature_required("enable_loans")
def loans():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "apply":
                principal = money(request.form.get("principal") or 0)
                tenure = int(request.form.get("tenure") or 12)
                purpose = (request.form.get("purpose") or "").strip()
                if principal <= 0:
                    flash("Invalid amount.", "error")
                else:
                    rate = money(get_config("loan_interest_rate", "10.5"))
                    monthly_rate = rate / 100 / 12
                    if monthly_rate == 0:
                        emi = money(principal / tenure)
                    else:
                        emi_val = float(principal) * float(monthly_rate) * (1 + float(monthly_rate)) ** tenure / ((1 + float(monthly_rate)) ** tenure - 1)
                        emi = money(emi_val)
                    total_owed = money(emi * tenure)
                    need_approval = get_config("require_loan_approval", "true").lower() in ("1", "true", "yes")

                    conn = get_db()
                    cur = conn.cursor()
                    status = "PENDING_APPROVAL" if need_approval else "ACTIVE"
                    cur.execute(
                        """INSERT INTO loans (user_id, principal, interest_rate, tenure_months, emi, total_owed, purpose, status, next_due_date)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_DATE + INTERVAL '1 month') RETURNING id""",
                        (user["id"], principal, rate, tenure, emi, total_owed, purpose, status),
                    )
                    loan_id = cur.fetchone()[0]
                    if need_approval:
                        import json
                        cur.execute(
                            "INSERT INTO approval_queue (type, payload_json, requester_id, amount, reference_id) VALUES ('LOAN',%s,%s,%s,%s)",
                            (json.dumps({"loan_id": loan_id, "principal": str(principal), "purpose": purpose}), user["id"], principal, ref()),
                        )
                        flash(f"Loan application of ₹{principal:,} submitted for approval. EMI would be ₹{emi:,}/month.", "success")
                    else:
                        cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (principal, user["id"]))
                        add_txn(conn, user["id"], "LOAN_DISBURSEMENT", principal, f"Loan #{loan_id} disbursed", "income")
                        flash(f"Loan of ₹{principal:,} approved! EMI: ₹{emi:,}/month for {tenure} months.", "success")
                    conn.commit()
                    conn.close()

            elif action == "repay":
                loan_id = int(request.form.get("loan_id") or 0)
                amount = money(request.form.get("amount") or 0)
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT total_owed, amount_paid FROM loans WHERE id=%s AND user_id=%s AND status='ACTIVE'",
                    (loan_id, user["id"]),
                )
                loan = cur.fetchone()
                if not loan:
                    flash("Invalid loan.", "error")
                    conn.close()
                else:
                    owed, paid = money(loan["total_owed"]), money(loan["amount_paid"])
                    pay = min(amount, owed - paid)
                    if pay <= 0:
                        flash("Invalid amount.", "error")
                        conn.close()
                    else:
                        ok = atomic_debit(conn, user["id"], pay)
                        if not ok:
                            conn.close()
                            flash("Insufficient balance.", "error")
                        else:
                            new_paid = paid + pay
                            status = "CLEARED" if new_paid >= owed else "ACTIVE"
                            cur.execute(
                                "UPDATE loans SET amount_paid=%s, status=%s WHERE id=%s",
                                (new_paid, status, loan_id),
                            )
                            add_txn(conn, user["id"], "LOAN_REPAYMENT", pay, f"Loan #{loan_id} repayment")
                            conn.commit()
                            conn.close()
                            msg = f"₹{pay:,} repaid."
                            if status == "CLEARED":
                                msg += " Loan fully cleared!"
                            flash(msg, "success")
        except Exception:
            logger.exception("Loan error")
            flash("Something went wrong.", "error")
        return redirect(url_for("loans"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, principal, emi, tenure_months, total_owed, amount_paid, status, next_due_date, timestamp FROM loans WHERE user_id=%s ORDER BY timestamp DESC",
        (user["id"],),
    )
    all_loans = cur.fetchall()
    conn.close()
    user = get_user(session["user_id"])
    return render_template("loans.html", user=user, loans=all_loans)


# ── Bills ─────────────────────────────────────────────────────────────────────

@app.route("/bills", methods=["GET", "POST"])
@login_required
@feature_required("enable_bills")
def bills():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "add":
                bill_type = (request.form.get("bill_type") or "").strip().upper()
                amount = money(request.form.get("amount") or 0)
                due_days = int(get_config("bill_due_days", "7"))
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO bills (user_id, bill_type, amount, due_date) VALUES (%s,%s,%s, CURRENT_DATE + %s * INTERVAL '1 day')",
                    (user["id"], bill_type, amount, due_days),
                )
                conn.commit()
                conn.close()
                flash("Bill added.", "success")

            elif action == "pay":
                bill_id = int(request.form.get("bill_id") or 0)
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT amount, bill_type FROM bills WHERE id=%s AND user_id=%s AND status IN ('PENDING','OVERDUE')",
                    (bill_id, user["id"]),
                )
                row = cur.fetchone()
                if not row:
                    flash("Invalid bill.", "error")
                    conn.close()
                else:
                    amt = money(row["amount"])
                    ok = atomic_debit(conn, user["id"], amt)
                    if not ok:
                        conn.close()
                        flash("Insufficient balance.", "error")
                    else:
                        add_txn(conn, user["id"], "BILL_PAYMENT", amt, f"{row['bill_type']} bill", "bills", "online")
                        cur.execute(
                            "UPDATE bills SET status='PAID', paid_at=NOW() WHERE id=%s",
                            (bill_id,),
                        )
                        update_budget(conn, user["id"], "bills", amt)
                        conn.commit()
                        conn.close()
                        flash("Bill paid.", "success")
        except Exception:
            logger.exception("Bills error")
            flash("Something went wrong.", "error")
        return redirect(url_for("bills"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, bill_type, amount, due_date, status FROM bills WHERE user_id=%s ORDER BY status, due_date",
        (user["id"],),
    )
    all_bills = cur.fetchall()
    conn.close()
    user = get_user(session["user_id"])
    return render_template("bills.html", user=user, bills=all_bills)


# ── Transfers ─────────────────────────────────────────────────────────────────

@app.route("/transfers", methods=["GET", "POST"])
@login_required
def transfers():
    user = get_user(session["user_id"])

    if request.method == "POST":
        t = request.form.get("transfer_type")
        try:
            if t == "self":
                direction = request.form.get("direction")
                amount = money(request.form.get("amount") or 0)
                conn = get_db()
                cur = conn.cursor()
                if direction == "to_savings":
                    ok = atomic_debit(conn, user["id"], amount)
                    if not ok:
                        conn.close()
                        flash("Insufficient wallet balance.", "error")
                    else:
                        cur.execute("UPDATE users SET savings_balance=savings_balance+%s WHERE id=%s", (amount, user["id"]))
                        cur.execute("INSERT INTO transfers (sender_id, receiver_info, amount, type, reference_id) VALUES (%s,'SELF-SAVINGS',%s,'SELF',%s)", (user["id"], amount, ref()))
                        conn.commit()
                        conn.close()
                        flash(f"₹{amount:,} moved to savings.", "success")
                elif direction == "to_wallet":
                    cur.execute(
                        "UPDATE users SET savings_balance=savings_balance-%s, balance=balance+%s WHERE id=%s AND savings_balance>=%s RETURNING id",
                        (amount, amount, user["id"], amount),
                    )
                    if cur.fetchone():
                        cur.execute("INSERT INTO transfers (sender_id, receiver_info, amount, type, reference_id) VALUES (%s,'SELF-WALLET',%s,'SELF',%s)", (user["id"], amount, ref()))
                        conn.commit()
                        conn.close()
                        flash(f"₹{amount:,} moved to wallet.", "success")
                    else:
                        conn.close()
                        flash("Insufficient savings balance.", "error")

            elif t == "bank":
                if not feature_enabled("enable_neft"):
                    flash("Bank transfers are currently disabled.", "error")
                    return redirect(url_for("transfers"))
                recipient_query = (request.form.get("recipient") or "").strip()
                amount = money(request.form.get("amount") or 0)
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, account_number FROM users WHERE username=%s OR account_number=%s",
                    (recipient_query, recipient_query),
                )
                rec = cur.fetchone()
                if not rec:
                    conn.close()
                    flash("Recipient not found.", "error")
                elif rec["id"] == user["id"]:
                    conn.close()
                    flash("Use Self Transfer for your own accounts.", "error")
                else:
                    high_val = money(get_config("high_value_threshold", "500000"))
                    if amount > high_val:
                        # Queue for approval
                        import json
                        cur.execute(
                            "INSERT INTO approval_queue (type, payload_json, requester_id, amount, reference_id) VALUES ('TRANSFER',%s,%s,%s,%s)",
                            (json.dumps({"from": user["id"], "to": rec["id"], "amount": str(amount), "channel": "BANK"}), user["id"], amount, ref()),
                        )
                        ok = atomic_debit(conn, user["id"], amount)
                        if not ok:
                            conn.close()
                            flash("Insufficient balance.", "error")
                        else:
                            conn.commit()
                            conn.close()
                            flash(f"₹{amount:,} transfer queued for admin approval (high-value).", "success")
                    else:
                        ok = atomic_debit(conn, user["id"], amount)
                        if not ok:
                            conn.close()
                            flash("Insufficient balance.", "error")
                        else:
                            atomic_credit(conn, rec["id"], amount)
                            r_id = ref()
                            add_txn(conn, user["id"], "TRANSFER_OUT", amount, f"To {rec['username']}", "transfers", "bank", rec["id"])
                            add_txn(conn, rec["id"], "TRANSFER_IN", amount, f"From {user['name']}", "income", "bank", user["id"])
                            cur.execute(
                                "INSERT INTO transfers (sender_id, receiver_id, receiver_info, amount, type, reference_id) VALUES (%s,%s,%s,%s,'BANK',%s)",
                                (user["id"], rec["id"], rec["username"], amount, r_id),
                            )
                            conn.commit()
                            conn.close()
                            flash(f"₹{amount:,} sent to {rec['username']}.", "success")

            elif t == "upi":
                upi_id = (request.form.get("upi_id") or "").strip()
                amount = money(request.form.get("amount") or 0)
                conn = get_db()
                ok = atomic_debit(conn, user["id"], amount)
                if not ok:
                    conn.close()
                    flash("Insufficient balance.", "error")
                else:
                    add_txn(conn, user["id"], "UPI_TRANSFER", amount, f"UPI to {upi_id}", "transfers", "upi")
                    conn.cursor().execute(
                        "INSERT INTO transfers (sender_id, receiver_info, amount, type, reference_id) VALUES (%s,%s,%s,'UPI',%s)",
                        (user["id"], upi_id, amount, ref()),
                    )
                    conn.commit()
                    conn.close()
                    flash(f"₹{amount:,} sent to {upi_id}.", "success")

            elif t == "international":
                if not feature_enabled("enable_international_transfers"):
                    flash("International transfers are currently disabled.", "error")
                    return redirect(url_for("transfers"))
                currency = request.form.get("currency", "USD")
                foreign_amt = money(request.form.get("foreign_amount") or 0)
                rate = get_fx_rate(currency)
                if not rate:
                    flash("Unsupported currency.", "error")
                    return redirect(url_for("transfers"))
                flat_fee = money(get_config("intl_flat_fee", "50"))
                spread_pct = money(get_config("intl_spread_pct", "1.0"))
                spread = (foreign_amt * rate * spread_pct / 100).quantize(Decimal("0.01"))
                inr = (foreign_amt * rate + flat_fee + spread).quantize(Decimal("0.01"))

                conn = get_db()
                ok = atomic_debit(conn, user["id"], inr)
                if not ok:
                    conn.close()
                    flash(f"Insufficient balance. Need ₹{inr:,} (inc. fees).", "error")
                else:
                    add_txn(conn, user["id"], "INTL_TRANSFER", inr, f"{currency} {foreign_amt}", "transfers", "international")
                    conn.cursor().execute(
                        "INSERT INTO transfers (sender_id, receiver_info, amount, fee, currency, fx_rate, type, reference_id) VALUES (%s,%s,%s,%s,%s,%s,'INTERNATIONAL',%s)",
                        (user["id"], currency, inr, flat_fee + spread, currency, rate, ref()),
                    )
                    conn.commit()
                    conn.close()
                    flash(f"{currency} {foreign_amt} = ₹{inr:,} (rate {rate}, fee ₹{flat_fee + spread}) transferred.", "success")

            elif t == "neft":
                if not feature_enabled("enable_neft"):
                    flash("NEFT transfers are currently disabled.", "error")
                    return redirect(url_for("transfers"))
                recipient_query = (request.form.get("recipient") or "").strip()
                amount = money(request.form.get("amount") or 0)
                fee = money(get_config("neft_fee", "5"))
                total = amount + fee
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username FROM users WHERE username=%s OR account_number=%s",
                    (recipient_query, recipient_query),
                )
                rec = cur.fetchone()
                if not rec:
                    conn.close()
                    flash("Recipient not found.", "error")
                else:
                    ok = atomic_debit(conn, user["id"], total)
                    if not ok:
                        conn.close()
                        flash(f"Insufficient balance. Need ₹{total:,} (₹{fee} NEFT fee).", "error")
                    else:
                        atomic_credit(conn, rec["id"], amount)
                        add_txn(conn, user["id"], "NEFT_TRANSFER", total, f"NEFT to {rec['username']} (₹{fee} fee)", "transfers", "neft", rec["id"])
                        add_txn(conn, rec["id"], "TRANSFER_IN", amount, f"NEFT from {user['name']}", "income", "neft", user["id"])
                        cur.execute(
                            "INSERT INTO transfers (sender_id, receiver_id, receiver_info, amount, fee, type, reference_id) VALUES (%s,%s,%s,%s,%s,'NEFT',%s)",
                            (user["id"], rec["id"], rec["username"], amount, fee, ref()),
                        )
                        conn.commit()
                        conn.close()
                        flash(f"NEFT of ₹{amount:,} to {rec['username']} done (₹{fee} fee).", "success")

            elif t == "issue_cheque":
                if not feature_enabled("enable_cheques"):
                    flash("Cheques are currently disabled.", "error")
                    return redirect(url_for("transfers"))
                receiver_name = (request.form.get("receiver") or "").strip()
                amount = money(request.form.get("amount") or 0)
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username=%s", (receiver_name,))
                rec = cur.fetchone()
                if not rec:
                    conn.close()
                    flash("Recipient user not found.", "error")
                else:
                    ok = atomic_debit(conn, user["id"], amount)
                    if not ok:
                        conn.close()
                        flash("Insufficient balance.", "error")
                    else:
                        chq_no = "CHQ" + str(random.randint(100000, 999999))
                        cur.execute(
                            "INSERT INTO cheques (issuer_id, receiver_name, receiver_id, cheque_number, amount) VALUES (%s,%s,%s,%s,%s)",
                            (user["id"], receiver_name, rec["id"], chq_no, amount),
                        )
                        conn.commit()
                        conn.close()
                        flash(f"Cheque {chq_no} for ₹{amount:,} issued to {receiver_name}. Funds held.", "success")

            elif t == "approve_cheque":
                cheque_id = int(request.form.get("cheque_id") or 0)
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT issuer_id, amount, cheque_number FROM cheques WHERE id=%s AND receiver_id=%s AND status='PENDING'",
                    (cheque_id, user["id"]),
                )
                row = cur.fetchone()
                if not row:
                    conn.close()
                    flash("Invalid cheque.", "error")
                else:
                    atomic_credit(conn, user["id"], money(row["amount"]))
                    cur.execute("UPDATE cheques SET status='CLEARED', cleared_at=NOW() WHERE id=%s", (cheque_id,))
                    add_txn(conn, user["id"], "CHEQUE_RECEIVED", money(row["amount"]), f"Cheque {row['cheque_number']} cleared", "income")
                    conn.commit()
                    conn.close()
                    flash(f"Cheque cleared. ₹{money(row['amount']):,} added to wallet.", "success")

        except Exception:
            logger.exception("Transfer error")
            flash("Something went wrong.", "error")
        return redirect(url_for("transfers"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT receiver_info, amount, type, timestamp, reference_id FROM transfers WHERE sender_id=%s ORDER BY timestamp DESC LIMIT 10",
        (user["id"],),
    )
    recent_transfers = cur.fetchall()
    cur.execute(
        "SELECT id, issuer_id, amount, issued_at, cheque_number FROM cheques WHERE receiver_id=%s AND status='PENDING'",
        (user["id"],),
    )
    pending_cheques = cur.fetchall()
    cur.execute(
        "SELECT base, rate FROM fx_rates WHERE quote='INR' ORDER BY base",
    )
    fx_rates = {row["base"]: money(row["rate"]) for row in cur.fetchall()}
    conn.close()
    user = get_user(session["user_id"])
    return render_template("transfers.html", user=user, recent_transfers=recent_transfers, pending_cheques=pending_cheques, fx_rates=fx_rates)


# ── PFM ───────────────────────────────────────────────────────────────────────

@app.route("/pfm", methods=["GET", "POST"])
@login_required
def pfm():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        conn = get_db()
        cur = conn.cursor()
        try:
            if action == "add_goal":
                name = (request.form.get("goal_name") or "").strip()
                target = money(request.form.get("target_amount") or 0)
                deadline = request.form.get("deadline") or None
                cur.execute(
                    "INSERT INTO goals (user_id, goal_name, target_amount, deadline) VALUES (%s,%s,%s,%s)",
                    (user["id"], name, target, deadline),
                )
                conn.commit()
                flash("Goal created.", "success")

            elif action == "contribute":
                goal_id = int(request.form.get("goal_id") or 0)
                amount = money(request.form.get("amount") or 0)
                ok = atomic_debit(conn, user["id"], amount)
                if not ok:
                    flash("Insufficient balance.", "error")
                else:
                    cur.execute(
                        "UPDATE goals SET saved_amount=saved_amount+%s WHERE id=%s AND user_id=%s",
                        (amount, goal_id, user["id"]),
                    )
                    add_txn(conn, user["id"], "GOAL_CONTRIBUTION", amount, "Goal contribution", "savings")
                    conn.commit()
                    flash(f"₹{amount:,} added to goal.", "success")

            elif action == "add_budget":
                category = (request.form.get("category") or "").strip()
                limit_val = money(request.form.get("limit_amount") or 0)
                cur.execute(
                    "INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s,%s,%s)",
                    (user["id"], category, limit_val),
                )
                conn.commit()
                flash("Budget set.", "success")

        except Exception:
            logger.exception("PFM error")
            flash("Something went wrong.", "error")
        conn.close()
        return redirect(url_for("pfm"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, goal_name, target_amount, saved_amount, deadline FROM goals WHERE user_id=%s AND status='ACTIVE'",
        (user["id"],),
    )
    goals = cur.fetchall()
    cur.execute(
        "SELECT id, category, monthly_limit, spent FROM budgets WHERE user_id=%s",
        (user["id"],),
    )
    budgets = cur.fetchall()
    conn.close()
    return render_template("pfm.html", user=user, goals=goals, budgets=budgets)


# ── Cards ─────────────────────────────────────────────────────────────────────

@app.route("/cards", methods=["GET", "POST"])
@login_required
def cards():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        conn = get_db()
        cur = conn.cursor()
        try:
            if action == "add":
                card_type = request.form.get("card_type", "DEBIT").upper()
                network = request.form.get("network", "VISA").upper()
                num = "4" + "".join([str(secrets.randbelow(10)) for _ in range(15)])
                cur.execute(
                    "INSERT INTO cards (user_id, card_number, holder_name, card_type, network, expiry_date) VALUES (%s,%s,%s,%s,%s,'2030-12-31')",
                    (user["id"], num, user["full_name"], card_type, network),
                )
                conn.commit()
                flash(f"{card_type} card ({network}) added: •••• {num[-4:]}", "success")

            elif action == "block":
                cur.execute("UPDATE cards SET status='BLOCKED' WHERE id=%s AND user_id=%s", (int(request.form.get("card_id", 0)), user["id"]))
                conn.commit()
                flash("Card blocked.", "success")

            elif action == "unblock":
                cur.execute("UPDATE cards SET status='ACTIVE' WHERE id=%s AND user_id=%s", (int(request.form.get("card_id", 0)), user["id"]))
                conn.commit()
                flash("Card unblocked.", "success")

            elif action == "renew":
                cur.execute("UPDATE cards SET expiry_date='2030-12-31', status='ACTIVE' WHERE id=%s AND user_id=%s", (int(request.form.get("card_id", 0)), user["id"]))
                conn.commit()
                flash("Card renewed.", "success")

        except Exception:
            logger.exception("Card error")
            flash("Something went wrong.", "error")
        conn.close()
        return redirect(url_for("cards"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, card_number, holder_name, card_type, network, status, expiry_date FROM cards WHERE user_id=%s ORDER BY created_at DESC",
        (user["id"],),
    )
    all_cards = cur.fetchall()
    conn.close()
    return render_template("cards.html", user=user, cards=all_cards)


# ── Investments ───────────────────────────────────────────────────────────────

@app.route("/investments", methods=["GET", "POST"])
@login_required
@feature_required("enable_investments")
def investments():
    user = get_user(session["user_id"])

    if request.method == "POST":
        action = request.form.get("action")
        conn = get_db()
        cur = conn.cursor()
        try:
            if action == "safe":
                inv_type = request.form.get("inv_type", "").upper()
                amount = money(request.form.get("amount") or 0)
                rate_map = {
                    "FD": money(get_config("fd_rate", "6.5")),
                    "BONDS": money(get_config("bonds_rate", "7.5")),
                    "MF": money(get_config("mf_rate", "11.0")),
                }
                if inv_type not in rate_map or amount <= 0:
                    flash("Invalid investment.", "error")
                    conn.close()
                elif not feature_enabled("enable_investments"):
                    flash("Investments are disabled.", "error")
                    conn.close()
                else:
                    ok = atomic_debit(conn, user["id"], amount)
                    if not ok:
                        conn.close()
                        flash("Insufficient balance.", "error")
                    else:
                        rate = rate_map[inv_type]
                        returns = (amount * rate / 100).quantize(Decimal("0.01"))
                        from datetime import timedelta
                        tenure_days = 365
                        mat_date = date.today() + timedelta(days=tenure_days)
                        cur.execute(
                            "INSERT INTO investments (user_id, type, amount, returns, current_value, maturity_date) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user["id"], inv_type, amount, returns, amount, mat_date),
                        )
                        add_txn(conn, user["id"], "INVESTMENT_PURCHASE", amount, f"{inv_type} investment", "investments")
                        conn.commit()
                        conn.close()
                        flash(f"Invested ₹{amount:,} in {inv_type}. Matures {mat_date}. Est. return: ₹{returns:,}/yr.", "success")

            elif action == "stock" and feature_enabled("enable_stocks"):
                symbol = (request.form.get("stock") or "").strip()
                qty = int(request.form.get("qty") or 0)
                price = get_stock_price(symbol)
                if not price or qty <= 0:
                    flash("Invalid stock or quantity.", "error")
                    conn.close()
                else:
                    total = (price * qty).quantize(Decimal("0.01"))
                    ok = atomic_debit(conn, user["id"], total)
                    if not ok:
                        conn.close()
                        flash("Insufficient balance.", "error")
                    else:
                        cur.execute(
                            "INSERT INTO investments (user_id, type, amount, quantity, unit_price_at_buy, current_value) VALUES (%s,%s,%s,%s,%s,%s)",
                            (user["id"], symbol, total, qty, price, total),
                        )
                        add_txn(conn, user["id"], "STOCK_PURCHASE", total, f"{qty}x {symbol} @ ₹{price}", "investments")
                        conn.commit()
                        conn.close()
                        flash(f"Bought {qty}× {symbol} at ₹{price} each. Total ₹{total:,}.", "success")

        except Exception:
            logger.exception("Investment error")
            flash("Something went wrong.", "error")
        conn.close()
        return redirect(url_for("investments"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT type, amount, quantity, unit_price_at_buy, current_value, returns, maturity_date, timestamp FROM investments WHERE user_id=%s AND redeemed_at IS NULL ORDER BY timestamp DESC",
        (user["id"],),
    )
    all_investments = cur.fetchall()
    cur.execute("SELECT symbol, name, price, day_change FROM stocks ORDER BY symbol")
    stocks_list = cur.fetchall()
    conn.close()
    safe_rates = {
        "FD": get_config("fd_rate", "6.5"),
        "BONDS": get_config("bonds_rate", "7.5"),
        "MF": get_config("mf_rate", "11.0"),
    }
    return render_template("investments.html", user=user, investments=all_investments, stocks=stocks_list, safe_rates=safe_rates)


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='USER'")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE status='ACTIVE' AND role='USER'")
    active_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE status='FROZEN'")
    frozen_users = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='DEPOSIT' AND timestamp > NOW() - INTERVAL '24 hours'")
    deposits_today = money(cur.fetchone()[0])
    cur.execute("SELECT COALESCE(SUM(total_owed - amount_paid), 0) FROM loans WHERE status='ACTIVE'")
    loans_outstanding = money(cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM approval_queue WHERE status='PENDING'")
    pending_approvals = cur.fetchone()[0]
    cur.execute("SELECT admin_id, action, target_type, target_id, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 20")
    recent_audit = cur.fetchall()
    conn.close()
    return render_template("admin/dashboard.html",
        total_users=total_users, active_users=active_users, frozen_users=frozen_users,
        deposits_today=deposits_today, loans_outstanding=loans_outstanding,
        pending_approvals=pending_approvals, recent_audit=recent_audit,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    q = request.args.get("q", "").strip()
    conn = get_db()
    cur = conn.cursor()
    if q:
        cur.execute(
            "SELECT id, username, full_name, email, role, status, balance, created_at FROM users WHERE username ILIKE %s OR full_name ILIKE %s OR email ILIKE %s ORDER BY created_at DESC",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
    else:
        cur.execute("SELECT id, username, full_name, email, role, status, balance, created_at FROM users ORDER BY created_at DESC")
    users_list = cur.fetchall()
    conn.close()
    return render_template("admin/users.html", users=users_list, q=q)


@app.route("/admin/users/<int:uid>")
@admin_required
def admin_user_detail(uid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    target = cur.fetchone()
    if not target:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))
    cur.execute("SELECT type, amount, timestamp, reference_id FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 20", (uid,))
    txns = cur.fetchall()
    cur.execute("SELECT id, principal, status, total_owed, amount_paid FROM loans WHERE user_id=%s ORDER BY timestamp DESC", (uid,))
    user_loans = cur.fetchall()
    cur.execute("SELECT id, card_number, card_type, status FROM cards WHERE user_id=%s", (uid,))
    user_cards = cur.fetchall()
    conn.close()
    return render_template("admin/user_detail.html", target=target, txns=txns, loans=user_loans, cards=user_cards)


@app.route("/admin/users/<int:uid>/freeze", methods=["POST"])
@admin_required
def admin_freeze_user(uid):
    reason = (request.form.get("reason") or "").strip() or "No reason given"
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET status='FROZEN', frozen_at=NOW(), frozen_reason=%s WHERE id=%s", (reason, uid))
        audit(conn, session["user_id"], "FREEZE_USER", "user", uid, str(row["status"]), "FROZEN")
        conn.commit()
        flash("User frozen.", "success")
    conn.close()
    return redirect(url_for("admin_user_detail", uid=uid))


@app.route("/admin/users/<int:uid>/unfreeze", methods=["POST"])
@admin_required
def admin_unfreeze_user(uid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET status='ACTIVE', frozen_at=NULL, frozen_reason=NULL WHERE id=%s", (uid,))
    audit(conn, session["user_id"], "UNFREEZE_USER", "user", uid)
    conn.commit()
    conn.close()
    flash("User unfrozen.", "success")
    return redirect(url_for("admin_user_detail", uid=uid))


@app.route("/admin/users/<int:uid>/credit", methods=["POST"])
@admin_required
def admin_credit_user(uid):
    try:
        amount = money(request.form.get("amount") or 0)
        conn = get_db()
        cur = conn.cursor()
        atomic_credit(conn, uid, amount)
        add_txn(conn, uid, "ADMIN_CREDIT", amount, "Manual credit by admin")
        audit(conn, session["user_id"], "CREDIT_USER", "user", uid, after=str(amount))
        conn.commit()
        conn.close()
        flash(f"₹{amount:,} credited.", "success")
    except Exception:
        logger.exception("Admin credit error")
        flash("Error.", "error")
    return redirect(url_for("admin_user_detail", uid=uid))


@app.route("/admin/config")
@admin_required
def admin_config():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key, value, category, description, updated_at FROM config ORDER BY category, key")
    config_rows = cur.fetchall()
    conn.close()
    return render_template("admin/config.html", config_rows=config_rows)


@app.route("/admin/config/<key>", methods=["POST"])
@admin_required
def admin_config_update(key):
    value = (request.form.get("value") or "").strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=%s", (key,))
    row = cur.fetchone()
    before = row["value"] if row else None
    cur.execute("UPDATE config SET value=%s, updated_by=%s, updated_at=NOW() WHERE key=%s", (value, session["user_id"], key))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO config (key,value,updated_by) VALUES (%s,%s,%s)", (key, value, session["user_id"]))
    audit(conn, session["user_id"], "UPDATE_CONFIG", "config", None, before, value)
    conn.commit()
    conn.close()
    flash(f"Config '{key}' updated.", "success")
    return redirect(url_for("admin_config"))


@app.route("/admin/queue")
@admin_required
def admin_queue():
    q_type = request.args.get("type", "LOAN")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT q.id, q.type, q.amount, q.created_at, q.reference_id, u.username FROM approval_queue q LEFT JOIN users u ON u.id=q.requester_id WHERE q.status='PENDING' AND q.type=%s ORDER BY q.created_at",
        (q_type,),
    )
    items = cur.fetchall()
    conn.close()
    return render_template("admin/queue.html", items=items, q_type=q_type)


@app.route("/admin/queue/<int:item_id>/approve", methods=["POST"])
@admin_required
def admin_queue_approve(item_id):
    import json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM approval_queue WHERE id=%s AND status='PENDING'", (item_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        flash("Item not found.", "error")
        return redirect(url_for("admin_queue"))

    payload = json.loads(item["payload_json"] or "{}")
    if item["type"] == "LOAN":
        loan_id = payload.get("loan_id")
        principal = money(payload.get("principal", 0))
        uid = item["requester_id"]
        cur.execute("UPDATE loans SET status='ACTIVE', approved_by=%s, approved_at=NOW() WHERE id=%s", (session["user_id"], loan_id))
        cur.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (principal, uid))
        add_txn(conn, uid, "LOAN_DISBURSEMENT", principal, f"Loan #{loan_id} approved")
        flash(f"Loan #{loan_id} approved and disbursed.", "success")

    elif item["type"] == "TRANSFER":
        from_id = payload.get("from")
        to_id = payload.get("to")
        amt = money(payload.get("amount", 0))
        atomic_credit(conn, to_id, amt)
        add_txn(conn, from_id, "TRANSFER_OUT", amt, "High-value transfer approved", "transfers", "bank", to_id)
        add_txn(conn, to_id, "TRANSFER_IN", amt, "High-value transfer received", "income", "bank", from_id)
        flash("Transfer approved and completed.", "success")

    cur.execute("UPDATE approval_queue SET status='APPROVED', reviewed_by=%s, reviewed_at=NOW() WHERE id=%s", (session["user_id"], item_id))
    audit(conn, session["user_id"], f"APPROVE_{item['type']}", "approval_queue", item_id)
    conn.commit()
    conn.close()
    return redirect(url_for("admin_queue"))


@app.route("/admin/queue/<int:item_id>/reject", methods=["POST"])
@admin_required
def admin_queue_reject(item_id):
    import json
    reason = (request.form.get("reason") or "").strip() or "No reason given"
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM approval_queue WHERE id=%s AND status='PENDING'", (item_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        flash("Item not found.", "error")
        return redirect(url_for("admin_queue"))

    payload = json.loads(item["payload_json"] or "{}")
    if item["type"] == "LOAN":
        loan_id = payload.get("loan_id")
        cur.execute("UPDATE loans SET status='REJECTED' WHERE id=%s", (loan_id,))

    elif item["type"] == "TRANSFER":
        # Refund held amount back to sender
        from_id = payload.get("from")
        amt = money(payload.get("amount", 0))
        atomic_credit(conn, from_id, amt)
        add_txn(conn, from_id, "TRANSFER_REFUND", amt, f"High-value transfer rejected: {reason}", "income")

    cur.execute("UPDATE approval_queue SET status='REJECTED', reviewed_by=%s, reviewed_at=NOW(), reason=%s WHERE id=%s", (session["user_id"], reason, item_id))
    audit(conn, session["user_id"], f"REJECT_{item['type']}", "approval_queue", item_id, after=reason)
    conn.commit()
    conn.close()
    flash("Item rejected.", "success")
    return redirect(url_for("admin_queue"))


@app.route("/admin/fx")
@admin_required
def admin_fx():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, base, quote, rate, updated_at FROM fx_rates ORDER BY base")
    rates = cur.fetchall()
    conn.close()
    return render_template("admin/fx.html", rates=rates)


@app.route("/admin/fx/update", methods=["POST"])
@admin_required
def admin_fx_update():
    base = (request.form.get("base") or "").strip().upper()
    rate = request.form.get("rate", "0").strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO fx_rates (base,quote,rate) VALUES (%s,'INR',%s) ON CONFLICT (base,quote) DO UPDATE SET rate=%s, updated_at=NOW()", (base, rate, rate))
    audit(conn, session["user_id"], "UPDATE_FX", "fx_rates", None, after=f"{base}/INR={rate}")
    conn.commit()
    conn.close()
    flash(f"FX {base}/INR updated to {rate}.", "success")
    return redirect(url_for("admin_fx"))


@app.route("/admin/stocks")
@admin_required
def admin_stocks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT symbol, name, price, day_change, updated_at FROM stocks ORDER BY symbol")
    stocks_list = cur.fetchall()
    conn.close()
    return render_template("admin/stocks.html", stocks=stocks_list)


@app.route("/admin/stocks/update", methods=["POST"])
@admin_required
def admin_stock_update():
    symbol = (request.form.get("symbol") or "").strip()
    price = request.form.get("price", "0").strip()
    name = (request.form.get("name") or symbol).strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO stocks (symbol,name,price) VALUES (%s,%s,%s) ON CONFLICT (symbol) DO UPDATE SET price=%s, updated_at=NOW()", (symbol, name, price, price))
    audit(conn, session["user_id"], "UPDATE_STOCK", "stocks", None, after=f"{symbol}={price}")
    conn.commit()
    conn.close()
    flash(f"{symbol} price updated.", "success")
    return redirect(url_for("admin_stocks"))


@app.route("/admin/stocks/tick", methods=["POST"])
@admin_required
def admin_stocks_tick():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT symbol, price FROM stocks")
    stocks_list = cur.fetchall()
    for s in stocks_list:
        delta = Decimal(str(round(random.uniform(-0.02, 0.02), 4)))
        new_price = max(Decimal("1"), (money(s["price"]) * (1 + delta)).quantize(Decimal("0.01")))
        day_change = ((new_price - money(s["price"])) / money(s["price"]) * 100).quantize(Decimal("0.01"))
        cur.execute("UPDATE stocks SET price=%s, day_change=%s, updated_at=NOW() WHERE symbol=%s", (new_price, day_change, s["symbol"]))
        # Update investment current_value for this stock
        cur.execute(
            "UPDATE investments SET current_value=quantity*%s WHERE type=%s AND redeemed_at IS NULL",
            (new_price, s["symbol"]),
        )
    audit(conn, session["user_id"], "SIMULATE_TICK", "stocks")
    conn.commit()
    conn.close()
    flash("Stock prices updated (tick simulated).", "success")
    return redirect(url_for("admin_stocks"))


@app.route("/admin/flags")
@admin_required
def admin_flags():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key, enabled, description FROM feature_flags ORDER BY key")
    flags = cur.fetchall()
    conn.close()
    return render_template("admin/flags.html", flags=flags)


@app.route("/admin/flags/toggle", methods=["POST"])
@admin_required
def admin_flag_toggle():
    key = (request.form.get("key") or "").strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE feature_flags SET enabled = NOT enabled WHERE key=%s RETURNING enabled", (key,))
    row = cur.fetchone()
    audit(conn, session["user_id"], "TOGGLE_FLAG", "feature_flags", None, after=f"{key}={row['enabled'] if row else '?'}")
    conn.commit()
    conn.close()
    flash(f"Flag '{key}' toggled.", "success")
    return redirect(url_for("admin_flags"))


@app.route("/admin/audit")
@admin_required
def admin_audit():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 30
    offset = (page - 1) * per_page
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM audit_log")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT a.id, u.username, a.action, a.target_type, a.target_id, a.before_json, a.after_json, a.timestamp FROM audit_log a LEFT JOIN users u ON u.id=a.admin_id ORDER BY a.timestamp DESC LIMIT %s OFFSET %s",
        (per_page, offset),
    )
    entries = cur.fetchall()
    conn.close()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("admin/audit.html", entries=entries, page=page, total_pages=total_pages)


@app.route("/admin/seed")
@admin_required
def admin_seed_page():
    return render_template("admin/seed.html")


@app.route("/admin/seed/run", methods=["POST"])
@admin_required
def admin_seed_run():
    import subprocess
    import sys
    try:
        result = subprocess.run([sys.executable, "seed.py"], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            flash("Demo data seeded successfully.", "success")
        else:
            flash(f"Seed failed: {result.stderr[:200]}", "error")
    except Exception as e:
        flash(f"Seed error: {e}", "error")
    return redirect(url_for("admin_seed_page"))


# ── API: recipient lookup for transfers ───────────────────────────────────────

@app.route("/api/lookup_user")
@login_required
def api_lookup_user():
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify(None)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, full_name, account_number FROM users WHERE (username=%s OR account_number=%s) AND id!=%s",
        (q, q, session["user_id"]),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return jsonify({"username": row["username"], "full_name": row["full_name"], "account": row["account_number"][-4:] if row["account_number"] else "N/A"})
    return jsonify(None)


if __name__ == "__main__":
    app.run(debug=True)
