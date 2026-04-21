import os
import random
import psycopg2
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash

load_dotenv()

app = Flask(__name__)
app.secret_key = 'prpbank_dev_secret'

db_url = os.getenv("DATABASE_URL")


def get_db():
    return psycopg2.connect(db_url)


def db_init():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            balance NUMERIC DEFAULT 0,
            password TEXT NOT NULL,
            savings_balance NUMERIC DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            amount NUMERIC NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            principal NUMERIC NOT NULL,
            interest_rate NUMERIC DEFAULT 5.0,
            total_owed NUMERIC NOT NULL,
            amount_paid NUMERIC DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ACTIVE',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            bill_type VARCHAR(50),
            amount NUMERIC,
            due_date DATE,
            status VARCHAR(20) DEFAULT 'PENDING'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            card_number TEXT UNIQUE,
            status VARCHAR(20) DEFAULT 'ACTIVE',
            expiry_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(30),
            amount NUMERIC,
            returns NUMERIC DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            goal_name TEXT,
            target_amount NUMERIC,
            saved_amount NUMERIC DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ACTIVE'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            category TEXT,
            monthly_limit NUMERIC,
            spent NUMERIC DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_info TEXT,
            amount NUMERIC,
            type VARCHAR(30),
            status VARCHAR(20) DEFAULT 'COMPLETED',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cheques (
            id SERIAL PRIMARY KEY,
            issuer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_name TEXT,
            amount NUMERIC,
            status VARCHAR(20) DEFAULT 'PENDING',
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, balance, savings_balance FROM users WHERE id=%s",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'name': row[1], 'balance': float(row[2]), 'savings': float(row[3] or 0)}
    return None


def login_required():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return None


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        pw = request.form['password'].strip()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name FROM users WHERE name=%s AND password=%s",
            (name, pw)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            session['user_id'] = row[0]
            session['user_name'] = row[1]
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        pw = request.form['password'].strip()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, password, savings_balance) VALUES (%s,%s,0)",
                (name, pw)
            )
            conn.commit()
            conn.close()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Username already taken.', 'error')
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, amount, timestamp FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 6",
        (user['id'],)
    )
    recent = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM loans WHERE user_id=%s AND status='ACTIVE'", (user['id'],))
    active_loans = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM bills WHERE user_id=%s AND status='PENDING'", (user['id'],))
    pending_bills = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(amount),0) FROM investments WHERE user_id=%s", (user['id'],))
    total_invested = float(cursor.fetchone()[0])
    conn.close()
    return render_template(
        'dashboard.html',
        user=user,
        recent=recent,
        active_loans=active_loans,
        pending_bills=pending_bills,
        total_invested=total_invested
    )


# ── Deposit / Withdraw ────────────────────────────────────────────────────────

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                flash('Enter a positive amount.', 'error')
            else:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, user['id']))
                cursor.execute(
                    "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'DEPOSIT',%s)",
                    (user['id'], amount)
                )
                conn.commit()
                conn.close()
                flash(f'₹{amount:,.2f} deposited!', 'success')
                return redirect(url_for('dashboard'))
        except Exception:
            flash('Invalid input.', 'error')
    return render_template('deposit.html', user=user)


@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                flash('Enter a positive amount.', 'error')
            elif amount > user['balance']:
                flash('Insufficient balance.', 'error')
            else:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user['id']))
                cursor.execute(
                    "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'WITHDRAWAL',%s)",
                    (user['id'], amount)
                )
                conn.commit()
                conn.close()
                flash(f'₹{amount:,.2f} withdrawn!', 'success')
                return redirect(url_for('dashboard'))
        except Exception:
            flash('Invalid input.', 'error')
    return render_template('withdraw.html', user=user)


# ── Transactions ──────────────────────────────────────────────────────────────

@app.route('/transactions')
def transactions():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, amount, timestamp FROM transactions WHERE user_id=%s ORDER BY timestamp DESC",
        (user['id'],)
    )
    history = cursor.fetchall()
    conn.close()
    return render_template('transactions.html', user=user, history=history)


# ── Loans ─────────────────────────────────────────────────────────────────────

@app.route('/loans', methods=['GET', 'POST'])
def loans():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'apply':
                principal = float(request.form['principal'])
                if principal <= 0:
                    flash('Invalid amount.', 'error')
                else:
                    total = round(principal * 1.05, 2)
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (principal, user['id']))
                    cursor.execute(
                        "INSERT INTO loans (user_id, principal, total_owed) VALUES (%s,%s,%s)",
                        (user['id'], principal, total)
                    )
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'LOAN_DISBURSEMENT',%s)",
                        (user['id'], principal)
                    )
                    conn.commit()
                    conn.close()
                    flash(f'Loan of ₹{principal:,.2f} approved! Total owed: ₹{total:,.2f}', 'success')

            elif action == 'repay':
                loan_id = int(request.form['loan_id'])
                amount = float(request.form['amount'])
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT total_owed, amount_paid FROM loans WHERE id=%s AND user_id=%s AND status='ACTIVE'",
                    (loan_id, user['id'])
                )
                loan = cursor.fetchone()
                if not loan:
                    flash('Invalid loan.', 'error')
                elif amount <= 0 or amount > user['balance']:
                    flash('Invalid amount.', 'error')
                else:
                    owed, paid = float(loan[0]), float(loan[1])
                    pay = min(amount, owed - paid)
                    new_paid = paid + pay
                    status = 'CLEARED' if new_paid >= owed else 'ACTIVE'
                    cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (pay, user['id']))
                    cursor.execute(
                        "UPDATE loans SET amount_paid=%s, status=%s WHERE id=%s",
                        (new_paid, status, loan_id)
                    )
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'LOAN_REPAYMENT',%s)",
                        (user['id'], pay)
                    )
                    conn.commit()
                    conn.close()
                    msg = f'₹{pay:,.2f} repaid!'
                    if status == 'CLEARED':
                        msg += ' Loan fully cleared!'
                    flash(msg, 'success')

        except Exception as e:
            flash(f'Error: {e}', 'error')
        return redirect(url_for('loans'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, principal, total_owed, amount_paid, status, timestamp FROM loans WHERE user_id=%s ORDER BY timestamp DESC",
        (user['id'],)
    )
    all_loans = cursor.fetchall()
    conn.close()
    user = get_user(session['user_id'])
    return render_template('loans.html', user=user, loans=all_loans)


# ── Bills ─────────────────────────────────────────────────────────────────────

@app.route('/bills', methods=['GET', 'POST'])
def bills():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                bill_type = request.form['bill_type'].strip().upper()
                amount = float(request.form['amount'])
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bills (user_id, bill_type, amount, due_date) VALUES (%s,%s,%s, CURRENT_DATE + INTERVAL '7 days')",
                    (user['id'], bill_type, amount)
                )
                conn.commit()
                conn.close()
                flash('Bill added!', 'success')

            elif action == 'pay':
                bill_id = int(request.form['bill_id'])
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT amount FROM bills WHERE id=%s AND user_id=%s AND status='PENDING'",
                    (bill_id, user['id'])
                )
                row = cursor.fetchone()
                if not row:
                    flash('Invalid bill.', 'error')
                elif float(row[0]) > user['balance']:
                    flash('Insufficient balance.', 'error')
                else:
                    amt = float(row[0])
                    cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amt, user['id']))
                    cursor.execute("UPDATE bills SET status='PAID' WHERE id=%s", (bill_id,))
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'BILL_PAYMENT',%s)",
                        (user['id'], amt)
                    )
                    conn.commit()
                    flash('Bill paid!', 'success')
                conn.close()

        except Exception as e:
            flash(f'Error: {e}', 'error')
        return redirect(url_for('bills'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, bill_type, amount, due_date, status FROM bills WHERE user_id=%s ORDER BY status, due_date",
        (user['id'],)
    )
    all_bills = cursor.fetchall()
    conn.close()
    user = get_user(session['user_id'])
    return render_template('bills.html', user=user, bills=all_bills)


# ── Transfers ─────────────────────────────────────────────────────────────────

@app.route('/transfers', methods=['GET', 'POST'])
def transfers():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        t = request.form.get('transfer_type')
        try:
            if t == 'self':
                direction = request.form['direction']
                amount = float(request.form['amount'])
                if direction == 'to_savings':
                    if amount <= 0 or amount > user['balance']:
                        flash('Invalid amount.', 'error')
                    else:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE users SET balance=balance-%s, savings_balance=savings_balance+%s WHERE id=%s",
                            (amount, amount, user['id'])
                        )
                        cursor.execute(
                            "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,'SELF-SAVINGS',%s,'SELF')",
                            (user['id'], amount)
                        )
                        conn.commit()
                        conn.close()
                        flash(f'₹{amount:,.2f} moved to savings!', 'success')
                elif direction == 'to_wallet':
                    if amount <= 0 or amount > user['savings']:
                        flash('Invalid amount.', 'error')
                    else:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE users SET balance=balance+%s, savings_balance=savings_balance-%s WHERE id=%s",
                            (amount, amount, user['id'])
                        )
                        cursor.execute(
                            "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,'SELF-WALLET',%s,'SELF')",
                            (user['id'], amount)
                        )
                        conn.commit()
                        conn.close()
                        flash(f'₹{amount:,.2f} moved to wallet!', 'success')

            elif t == 'bank':
                recipient = request.form['recipient'].strip()
                amount = float(request.form['amount'])
                if recipient == user['name']:
                    flash('Use Self Transfer for your own account.', 'error')
                elif amount <= 0 or amount > user['balance']:
                    flash('Invalid amount.', 'error')
                else:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE name=%s", (recipient,))
                    rec = cursor.fetchone()
                    if not rec:
                        flash('User not found.', 'error')
                    else:
                        cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user['id']))
                        cursor.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, rec[0]))
                        cursor.execute(
                            "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,'BANK')",
                            (user['id'], recipient, amount)
                        )
                        cursor.execute(
                            "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'TRANSFER_OUT',%s)",
                            (user['id'], amount)
                        )
                        conn.commit()
                        flash(f'₹{amount:,.2f} sent to {recipient}!', 'success')
                    conn.close()

            elif t == 'upi':
                upi_id = request.form['upi_id'].strip()
                amount = float(request.form['amount'])
                if amount <= 0 or amount > user['balance']:
                    flash('Invalid amount.', 'error')
                else:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user['id']))
                    cursor.execute(
                        "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,'UPI')",
                        (user['id'], upi_id, amount)
                    )
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'UPI_TRANSFER',%s)",
                        (user['id'], amount)
                    )
                    conn.commit()
                    conn.close()
                    flash(f'₹{amount:,.2f} sent to {upi_id}!', 'success')

            elif t == 'international':
                currency = request.form['currency']
                foreign_amt = float(request.form['foreign_amount'])
                rates = {'USD': 83, 'EUR': 90, 'GBP': 105}
                if currency not in rates:
                    flash('Invalid currency.', 'error')
                else:
                    inr = round(foreign_amt * rates[currency], 2)
                    if inr > user['balance']:
                        flash('Insufficient balance.', 'error')
                    else:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (inr, user['id']))
                        cursor.execute(
                            "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,'INTERNATIONAL')",
                            (user['id'], currency, inr)
                        )
                        cursor.execute(
                            "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'INTL_TRANSFER',%s)",
                            (user['id'], inr)
                        )
                        conn.commit()
                        conn.close()
                        flash(f'{currency} {foreign_amt:.2f} (₹{inr:,.2f}) transferred!', 'success')

            elif t == 'neft':
                recipient = request.form['recipient'].strip()
                amount = float(request.form['amount'])
                fee = 5.0
                total = amount + fee
                if amount <= 0 or total > user['balance']:
                    flash('Insufficient balance! (₹5 NEFT fee applies)', 'error')
                else:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE name=%s", (recipient,))
                    rec = cursor.fetchone()
                    if not rec:
                        flash('User not found.', 'error')
                    else:
                        cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, user['id']))
                        cursor.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amount, rec[0]))
                        cursor.execute(
                            "INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,'NEFT')",
                            (user['id'], recipient, amount)
                        )
                        cursor.execute(
                            "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'NEFT_TRANSFER',%s)",
                            (user['id'], total)
                        )
                        conn.commit()
                        flash(f'NEFT of ₹{amount:,.2f} to {recipient} done! (₹5 fee)', 'success')
                    conn.close()

            elif t == 'issue_cheque':
                receiver = request.form['receiver'].strip()
                amount = float(request.form['amount'])
                if amount <= 0 or amount > user['balance']:
                    flash('Invalid amount.', 'error')
                else:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO cheques (issuer_id, receiver_name, amount) VALUES (%s,%s,%s)",
                        (user['id'], receiver, amount)
                    )
                    conn.commit()
                    conn.close()
                    flash('Cheque issued!', 'success')

            elif t == 'approve_cheque':
                cheque_id = int(request.form['cheque_id'])
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT issuer_id, amount FROM cheques WHERE id=%s AND receiver_name=%s AND status='PENDING'",
                    (cheque_id, user['name'])
                )
                row = cursor.fetchone()
                if not row:
                    flash('Invalid cheque.', 'error')
                else:
                    issuer_id, amt = row[0], float(row[1])
                    cursor.execute("SELECT balance FROM users WHERE id=%s", (issuer_id,))
                    issuer_bal = float(cursor.fetchone()[0])
                    if issuer_bal < amt:
                        flash('Issuer has insufficient funds.', 'error')
                    else:
                        cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amt, issuer_id))
                        cursor.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (amt, user['id']))
                        cursor.execute("UPDATE cheques SET status='CLEARED' WHERE id=%s", (cheque_id,))
                        cursor.execute(
                            "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'CHEQUE_RECEIVED',%s)",
                            (user['id'], amt)
                        )
                        conn.commit()
                        flash(f'Cheque approved! ₹{amt:,.2f} added to wallet.', 'success')
                conn.close()

        except Exception as e:
            flash(f'Error: {e}', 'error')
        return redirect(url_for('transfers'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT receiver_info, amount, type, timestamp FROM transfers WHERE sender_id=%s ORDER BY timestamp DESC LIMIT 10",
        (user['id'],)
    )
    recent_transfers = cursor.fetchall()
    cursor.execute(
        "SELECT id, issuer_id, amount, issued_at FROM cheques WHERE receiver_name=%s AND status='PENDING'",
        (user['name'],)
    )
    pending_cheques = cursor.fetchall()
    conn.close()
    user = get_user(session['user_id'])
    return render_template('transfers.html', user=user, recent_transfers=recent_transfers, pending_cheques=pending_cheques)


# ── PFM ───────────────────────────────────────────────────────────────────────

@app.route('/pfm', methods=['GET', 'POST'])
def pfm():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db()
        cursor = conn.cursor()
        try:
            if action == 'add_goal':
                name = request.form['goal_name'].strip()
                target = float(request.form['target_amount'])
                cursor.execute(
                    "INSERT INTO goals (user_id, goal_name, target_amount) VALUES (%s,%s,%s)",
                    (user['id'], name, target)
                )
                conn.commit()
                flash('Goal created!', 'success')

            elif action == 'contribute':
                goal_id = int(request.form['goal_id'])
                amount = float(request.form['amount'])
                if amount <= 0 or amount > user['balance']:
                    flash('Invalid amount.', 'error')
                else:
                    cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user['id']))
                    cursor.execute(
                        "UPDATE goals SET saved_amount=saved_amount+%s WHERE id=%s AND user_id=%s",
                        (amount, goal_id, user['id'])
                    )
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s,'GOAL_CONTRIBUTION',%s)",
                        (user['id'], amount)
                    )
                    conn.commit()
                    flash(f'₹{amount:,.2f} added to goal!', 'success')

            elif action == 'add_budget':
                category = request.form['category'].strip()
                limit = float(request.form['limit_amount'])
                cursor.execute(
                    "INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s,%s,%s)",
                    (user['id'], category, limit)
                )
                conn.commit()
                flash('Budget set!', 'success')

        except Exception as e:
            flash(f'Error: {e}', 'error')
        conn.close()
        return redirect(url_for('pfm'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, goal_name, target_amount, saved_amount FROM goals WHERE user_id=%s AND status='ACTIVE'",
        (user['id'],)
    )
    goals = cursor.fetchall()
    cursor.execute(
        "SELECT id, category, monthly_limit, spent FROM budgets WHERE user_id=%s",
        (user['id'],)
    )
    budgets = cursor.fetchall()
    conn.close()
    return render_template('pfm.html', user=user, goals=goals, budgets=budgets)


# ── Cards ─────────────────────────────────────────────────────────────────────

@app.route('/cards', methods=['GET', 'POST'])
def cards():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db()
        cursor = conn.cursor()
        try:
            if action == 'add':
                num = str(random.randint(1000000000000000, 9999999999999999))
                cursor.execute(
                    "INSERT INTO cards (user_id, card_number, expiry_date) VALUES (%s,%s,'2030-12-31')",
                    (user['id'], num)
                )
                conn.commit()
                flash(f'Card added: {num[:4]} **** **** {num[-4:]}', 'success')

            elif action == 'block':
                cursor.execute(
                    "UPDATE cards SET status='BLOCKED' WHERE id=%s AND user_id=%s",
                    (int(request.form['card_id']), user['id'])
                )
                conn.commit()
                flash('Card blocked.', 'success')

            elif action == 'unblock':
                cursor.execute(
                    "UPDATE cards SET status='ACTIVE' WHERE id=%s AND user_id=%s",
                    (int(request.form['card_id']), user['id'])
                )
                conn.commit()
                flash('Card unblocked.', 'success')

            elif action == 'renew':
                cursor.execute(
                    "UPDATE cards SET expiry_date='2035-12-31', status='ACTIVE' WHERE id=%s AND user_id=%s",
                    (int(request.form['card_id']), user['id'])
                )
                conn.commit()
                flash('Card renewed until 2035.', 'success')

        except Exception as e:
            flash(f'Error: {e}', 'error')
        conn.close()
        return redirect(url_for('cards'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, card_number, status, expiry_date FROM cards WHERE user_id=%s ORDER BY created_at DESC",
        (user['id'],)
    )
    all_cards = cursor.fetchall()
    conn.close()
    return render_template('cards.html', user=user, cards=all_cards)


# ── Investments ───────────────────────────────────────────────────────────────

@app.route('/investments', methods=['GET', 'POST'])
def investments():
    redir = login_required()
    if redir:
        return redir
    user = get_user(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db()
        cursor = conn.cursor()
        try:
            if action == 'safe':
                inv_type = request.form['inv_type']
                amount = float(request.form['amount'])
                rates = {'FD': 0.05, 'BONDS': 0.07, 'MF': 0.10}
                if inv_type not in rates or amount <= 0 or amount > user['balance']:
                    flash('Invalid investment.', 'error')
                else:
                    returns = round(amount * rates[inv_type], 2)
                    cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (amount, user['id']))
                    cursor.execute(
                        "INSERT INTO investments (user_id, type, amount, returns) VALUES (%s,%s,%s,%s)",
                        (user['id'], inv_type, amount, returns)
                    )
                    conn.commit()
                    flash(f'Invested ₹{amount:,.2f} in {inv_type}! Expected return: ₹{returns:,.2f}', 'success')

            elif action == 'stock':
                stock = request.form['stock']
                qty = int(request.form['qty'])
                prices = {'TechCorp': 100, 'GreenEnergy': 200, 'FinBank': 150}
                if stock not in prices or qty <= 0:
                    flash('Invalid stock.', 'error')
                else:
                    total = prices[stock] * qty
                    if total > user['balance']:
                        flash('Insufficient balance.', 'error')
                    else:
                        predicted = round(prices[stock] * random.uniform(0.8, 1.5) * qty, 2)
                        returns = round(predicted - total, 2)
                        cursor.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, user['id']))
                        cursor.execute(
                            "INSERT INTO investments (user_id, type, amount, returns) VALUES (%s,%s,%s,%s)",
                            (user['id'], stock, total, returns)
                        )
                        conn.commit()
                        flash(f'Bought {qty}x {stock} for ₹{total:,}! Predicted value: ₹{predicted:,.2f}', 'success')

        except Exception as e:
            flash(f'Error: {e}', 'error')
        conn.close()
        return redirect(url_for('investments'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, amount, returns, timestamp FROM investments WHERE user_id=%s ORDER BY timestamp DESC",
        (user['id'],)
    )
    all_investments = cursor.fetchall()
    conn.close()
    return render_template('investments.html', user=user, investments=all_investments)


db_init()

if __name__ == '__main__':
    app.run(debug=True)
