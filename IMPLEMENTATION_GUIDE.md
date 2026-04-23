# PRP Bank — Implementation Guide
> What has been done, what still needs to be done, and exactly how to do each remaining step.

---

## STATUS: ~40% complete

### ✅ DONE (already applied to files)

| File | Change |
|---|---|
| `app.py` | Added `import json` |
| `app.py` | Replaced `DEMO_USERS` list with `DEMO_PASSWORDS` dict + `get_demo_users()` function that queries DB |
| `app.py` | `get_user()` now returns `branch_code` |
| `app.py` | `db_init()` — added `branch_code TEXT` column to users table + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration |
| `app.py` | `db_init()` — upserts loan-rate config keys at the end (home 8.5%, auto 9.5%, personal 12%, education 10%) |
| `app.py` | `seed_demo_data()` — added `branch_code` to all 4 user INSERTs (BR001/BR001/BR002/BR003) |
| `app.py` | `seed_demo_data()` — added loan rate config keys to `config_data` with `ON CONFLICT DO NOTHING` |
| `app.py` | `/loans` apply action — real EMI formula, loan type + tenure from form, creates PENDING loan + approval record with JSON detail containing `loan_id` |
| `app.py` | `/admin/approvals/<aid>/approve` — reads `kind` + `detail`, on `kind='loan'` parses loan_id from JSON, activates loan, credits balance, inserts LOAN_DISBURSEMENT txn |
| `app.py` | `/investments` — removed the `add_txn(...)` call that caused NameError (line 1608) |
| `app.py` | `/transfers` international — reads FX rate from `fx_rates` table instead of hardcoded dict |
| `app.py` | `/transfers` GET — queries `fx_rates` table and passes `fx_display` string to template |
| `app.py` | `/cards` — added `action == 'delete'` branch (checks for outstanding credit balance before deleting) |
| `app.py` | `/loans` GET — passes `loan_rates` dict to template for live EMI preview |
| `app.py` | `login` route — uses `get_demo_users()` instead of `DEMO_USERS` |
| `app.py` | Startup — `seed_demo_data()` now gated on `AUTO_SEED=1` env var (default=1 so existing deploys still work) |
| `static/css/style.css` | Added `.tab-content { display:none }` + `.tab-content.active { display:block }` — **this is the main tab-switching fix** |
| `static/css/style.css` | Added `.cards-grid` (3-col grid, responsive 2-col at 1024px, 1-col at 600px) |
| `static/css/style.css` | Added `.card-tile`, `.card-tile:hover`, `.card-tile.expanded` |
| `static/css/style.css` | Added `.card-actions` (hidden by default, flex on `.card-tile.expanded`) |
| `static/css/style.css` | Added `.card-bank`, `.card-footer` |
| `static/css/style.css` | Added `.bill-confirm-modal`, `.bill-confirm-box`, `.bill-confirm-actions` |
| `templates/login.html` | **Full rewrite** — 4 credential cards in 2×2 grid from DB, bank info chips (A/C, IFSC, branch code, branch), removed all fake security badges, removed hardcoded credentials |

---

## ❌ REMAINING — Do these in order

---

### 1. `templates/cards.html` — 3-col grid, click-to-expand, delete button

Replace the entire file content with this:

```html
{% extends "base.html" %}
{% block title %} — Cards{% endblock %}
{% block page_title %}<h1>Cards</h1>{% endblock %}

{% block content %}
<!-- Issue New Card -->
<div class="inst-card mb-24">
  <div class="inst-card-header"><span>Issue a New Card</span></div>
  <div class="inst-card-body">
    <form method="POST" action="{{ url_for('cards') }}">
      <input type="hidden" name="action" value="issue">
      <div class="grid grid-2" style="gap:12px;">
        <div class="form-group">
          <label>Card Type</label>
          <select name="card_type" required>
            <option value="Debit">Debit</option>
            <option value="Credit">Credit</option>
          </select>
        </div>
        <div class="form-group">
          <label>Brand</label>
          <select name="brand" required>
            <option value="Visa">Visa</option>
            <option value="Mastercard">Mastercard</option>
            <option value="RuPay">RuPay</option>
          </select>
        </div>
      </div>
      <button type="submit" class="btn btn-primary">Issue Card</button>
    </form>
  </div>
</div>

<!-- Cards Grid -->
{% if cards %}
<div class="cards-grid">
  {% for card in cards %}
  <div class="card-tile" onclick="toggleCard(this, event)">
    <!-- Card face — always visible -->
    <div class="card-visual{% if card[5] == 'BLOCKED' %} blocked{% endif %}">
      <div class="card-bank">PRP BANK &nbsp;·&nbsp; {{ card[2] }}</div>
      <div class="card-number">**** **** **** {{ card[4] }}</div>
      <div class="card-footer">
        <div>
          <div style="font-size:9px;opacity:0.6;letter-spacing:0.05em;margin-bottom:2px;">EXPIRES</div>
          <div>{{ card[8]|dateformat }}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:9px;opacity:0.6;letter-spacing:0.05em;margin-bottom:2px;">TYPE</div>
          <div>{{ card[3] }}</div>
        </div>
      </div>
    </div>

    <!-- Usage progress bar — always visible for credit cards -->
    {% if card[3] == 'Credit' and card[6] > 0 %}
    <div style="margin-top:8px;">
      <div class="progress-bar">
        <div class="progress-fill{% if card[7] / card[6] > 0.8 %} danger{% elif card[7] / card[6] > 0.5 %} warning{% else %} success{% endif %}"
             style="width:{{ [((card[7] / card[6]) * 100)|round(1), 100]|min }}%"></div>
      </div>
      <div class="flex-between" style="margin-top:4px;">
        <span class="text-dim" style="font-size:11px;">{{ card[7]|inr }} used</span>
        <span class="text-dim" style="font-size:11px;">Limit {{ card[6]|inr }}</span>
      </div>
    </div>
    {% endif %}

    <!-- Status badge — always visible -->
    <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;">
      {% if card[5] == 'ACTIVE' %}
        <span class="badge badge-green">ACTIVE</span>
      {% else %}
        <span class="badge badge-red">{{ card[5] }}</span>
      {% endif %}
      <span class="text-dim" style="font-size:11px;">Tap to manage</span>
    </div>

    <!-- Actions — revealed on click -->
    <div class="card-actions" onclick="event.stopPropagation()">
      <form method="POST" action="{{ url_for('cards') }}" style="display:inline;">
        <input type="hidden" name="action" value="toggle">
        <input type="hidden" name="card_id" value="{{ card[0] }}">
        {% if card[5] == 'ACTIVE' %}
          <button type="submit" class="btn btn-danger btn-sm">Block</button>
        {% else %}
          <button type="submit" class="btn btn-success btn-sm">Activate</button>
        {% endif %}
      </form>
      <form method="POST" action="{{ url_for('cards') }}" style="display:inline;"
            onsubmit="return confirm('Delete this card permanently?')">
        <input type="hidden" name="action" value="delete">
        <input type="hidden" name="card_id" value="{{ card[0] }}">
        <button type="submit" class="btn btn-sm" style="background:var(--surface-2);border:1px solid var(--border);color:var(--text-muted);">Delete</button>
      </form>
    </div>
  </div>
  {% endfor %}
</div>
{% else %}
<p class="empty-text">No cards issued yet. Create one above.</p>
{% endif %}

<script>
function toggleCard(tile, event) {
  if (event.target.tagName === 'BUTTON' || event.target.tagName === 'INPUT') return;
  var isOpen = tile.classList.contains('expanded');
  document.querySelectorAll('.card-tile.expanded').forEach(function(t) { t.classList.remove('expanded'); });
  if (!isOpen) tile.classList.add('expanded');
}
</script>
{% endblock %}
```

---

### 2. `templates/transfers.html` — Fix broken JS + replace hardcoded FX

**Find and delete lines 232–248** (the broken JS block at the bottom):
```js
// DELETE THIS ENTIRE BLOCK:
// Recipient name verification
var verifyTimer;
document.getElementById('bank-recipient').addEventListener('input', function() {
  ...
});
```

**Also replace the hardcoded FX info-box** (line 103):
```html
<!-- OLD: -->
<div class="info-box mb-16">USD ₹83.42 · EUR ₹90.15 · GBP ₹105.30</div>

<!-- NEW: -->
<div class="info-box mb-16">{{ fx_display }}</div>
```

The `<script>` block at the bottom should end with just `showTab` — no `getElementById('bank-recipient')`:
```html
<script>
function showTab(name, btn) {
  document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.tab').forEach(function(el) { el.classList.remove('active'); });
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}
</script>
```

---

### 3. `templates/bills.html` — Add confirmation modal

Replace the Pay button form with a button that opens a modal. Add the modal at the bottom. Full replacement:

```html
{% extends "base.html" %}
{% block title %} — Bills{% endblock %}
{% block page_title %}<h1>Bills</h1>{% endblock %}

{% block content %}
<div class="inst-card">
  <div class="inst-card-header">
    <span>All Bills</span>
    <span class="balance-chip">Wallet: {{ user.balance|inr }}</span>
  </div>
  <div class="inst-card-body" style="padding:0;">
    {% if bills %}
    <div style="overflow-x:auto;">
      <table class="inst-table">
        <thead>
          <tr>
            <th>Biller</th>
            <th>Category</th>
            <th>Amount</th>
            <th>Due Date</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {% for bill in bills %}
          <tr>
            <td>{{ bill[1] }}</td>
            <td class="text-muted">{{ bill[2] }}</td>
            <td class="amount">{{ bill[3]|inr }}</td>
            <td class="text-muted">{{ bill[4]|dateformat }}</td>
            <td>
              {% if bill[5] == 'PENDING' %}
                <span class="badge badge-yellow">{{ bill[5] }}</span>
              {% elif bill[5] == 'OVERDUE' %}
                <span class="badge badge-red">{{ bill[5] }}</span>
              {% elif bill[5] == 'PAID' %}
                <span class="badge badge-green">{{ bill[5] }}</span>
              {% else %}
                <span class="badge badge-blue">{{ bill[5] }}</span>
              {% endif %}
            </td>
            <td>
              {% if bill[5] in ('PENDING', 'OVERDUE') %}
              <button type="button" class="btn btn-success btn-sm"
                      onclick="openPayModal({{ bill[0] }}, '{{ bill[1]|replace("'","\\\'") }}', {{ bill[3] }})">
                Pay
              </button>
              {% else %}
              <span class="text-dim">—</span>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <p class="empty-text">No bills found.</p>
    {% endif %}
  </div>
</div>

<!-- Bill Pay Confirmation Modal -->
<div class="bill-confirm-modal" id="payModal">
  <div class="bill-confirm-box">
    <h3>Confirm Payment</h3>
    <div class="amount-display" id="modalAmount"></div>
    <div class="biller-name" id="modalBiller"></div>
    <p style="font-size:12px;color:var(--text-muted);margin-bottom:20px;">
      This amount will be deducted from your wallet balance ({{ user.balance|inr }}).
    </p>
    <form method="POST" action="{{ url_for('bills') }}" id="payForm">
      <input type="hidden" name="bill_id" id="modalBillId">
      <div class="bill-confirm-actions">
        <button type="submit" class="btn btn-success" style="flex:1;">Confirm Payment</button>
        <button type="button" class="btn" style="flex:1;background:var(--surface-2);border:1px solid var(--border);"
                onclick="closePayModal()">Cancel</button>
      </div>
    </form>
  </div>
</div>

<script>
function openPayModal(billId, biller, amount) {
  document.getElementById('modalBillId').value = billId;
  document.getElementById('modalBiller').textContent = biller;
  var formatted = '₹' + parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2});
  document.getElementById('modalAmount').textContent = formatted;
  document.getElementById('payModal').classList.add('active');
}
function closePayModal() {
  document.getElementById('payModal').classList.remove('active');
}
document.getElementById('payModal').addEventListener('click', function(e) {
  if (e.target === this) closePayModal();
});
</script>
{% endblock %}
```

---

### 4. `templates/loans.html` — Loan type, tenure, EMI preview, pending status

Replace the "Apply for a Loan" card body with this:

```html
<div class="inst-card-body">
  <form method="POST" action="{{ url_for('loans') }}">
    <input type="hidden" name="action" value="apply">
    <div class="form-group">
      <label>Loan Type</label>
      <select name="loan_type" id="loanType" onchange="calcEmi()" required>
        <option value="Personal">Personal  ({{ loan_rates.Personal }}% p.a.)</option>
        <option value="Home">Home  ({{ loan_rates.Home }}% p.a.)</option>
        <option value="Auto">Auto  ({{ loan_rates.Auto }}% p.a.)</option>
        <option value="Education">Education  ({{ loan_rates.Education }}% p.a.)</option>
      </select>
    </div>
    <div class="form-group">
      <label>Principal Amount (₹)</label>
      <input type="number" name="principal" id="loanPrincipal" step="1000" min="10000"
             placeholder="e.g. 500000" required oninput="calcEmi()">
    </div>
    <div class="form-group">
      <label>Tenure</label>
      <select name="term_months" id="loanTenure" onchange="calcEmi()" required>
        <option value="6">6 months</option>
        <option value="12" selected>12 months</option>
        <option value="24">24 months</option>
        <option value="36">36 months</option>
        <option value="60">60 months</option>
      </select>
    </div>
    <div class="info-box mb-16" id="emiPreview" style="display:none;">
      EMI: <strong id="emiValue">—</strong> /month &nbsp;·&nbsp; Total: <strong id="totalValue">—</strong>
    </div>
    <div class="info-box mb-16" style="font-size:12px;color:var(--text-muted);">
      Loan applications require admin approval. Funds are credited after approval.
    </div>
    <button type="submit" class="btn btn-primary btn-block">Apply for Loan</button>
  </form>
</div>
```

Add the JS block at the bottom of the template (before `{% endblock %}`):
```html
<script>
var loanRates = {{ loan_rates | tojson }};

function calcEmi() {
  var p = parseFloat(document.getElementById('loanPrincipal').value) || 0;
  var type = document.getElementById('loanType').value;
  var n = parseInt(document.getElementById('loanTenure').value) || 12;
  var preview = document.getElementById('emiPreview');
  if (p <= 0) { preview.style.display = 'none'; return; }
  var annual = loanRates[type] || 12;
  var r = annual / 12 / 100;
  var emi = r > 0
    ? p * r * Math.pow(1+r,n) / (Math.pow(1+r,n) - 1)
    : p / n;
  var total = emi * n;
  function fmt(v) { return '₹' + v.toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2}); }
  document.getElementById('emiValue').textContent = fmt(emi);
  document.getElementById('totalValue').textContent = fmt(total);
  preview.style.display = 'block';
}
</script>
```

Also change the status badge for PENDING loans — in the loan history table, `loan[9] == 'PENDING'` should show `badge-blue` (already does — just ensure it's there).

---

### 5. `templates/base.html` — Remove hardcoded version string

Find the line with `v1.4.2 · prod` and `All systems` in the sidebar footer. It looks like:
```html
v1.4.2 · prod
```
Replace the version badge text with just `PRP Bank` or remove that footer div entirely.

---

### 6. `seed.py` — Rewrite as standalone seeder

Delete everything in the current `seed.py` and replace with:

```python
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
```

---

### 7. `templates/base.html` — Remove hardcoded version string

Find the line with `v1.4.2 · prod` and remove/replace it. It will be near the bottom of the sidebar. Either delete that div or replace with just `PRP Bank`.

---

### 8. `demo_personas.py` — Delete the file

```bash
rm /Users/kk/Desktop/prpbankproject/demo_personas.py
```

---

## QUICK-START AFTER RESUMING

```bash
cd /Users/kk/Desktop/prpbankproject

# 1. Reset and re-seed the DB with the new seed script
python seed.py --reset

# 2. Start the app
AUTO_SEED=0 flask run

# 3. Verify row counts
python seed.py --verify
```

---

## VERIFICATION CHECKLIST

- [ ] Login page: 4 cards (Kahaan, Zaid, Nishad, Siddhesh) in a 2×2 grid. Each shows A/C number, IFSC, branch, branch code. Clicking autofills form. No "256-bit AES" or "218 branches" text anywhere.
- [ ] Transfers page: Clicking tabs (Self, Bank, UPI, International, NEFT, Cheque) shows ONLY that tab's content. FX rates come from DB, not hardcoded.
- [ ] Cards page: 3-column grid. Cards look like bank cards (gradient, number, expiry). Actions (Block/Activate/Delete) hidden until card is clicked.
- [ ] Bills page: Pay button opens a modal with biller name + amount. Confirming deducts wallet balance.
- [ ] Loans page: Type + Tenure dropdowns. Live EMI preview updates as you type. Submitting creates a PENDING loan (no instant credit). Admin must approve in `/admin/approvals`.
- [ ] Investments page: Buying FD/Bonds/MF works without crashing (NameError is fixed).
- [ ] Admin approve loan: Loan switches to ACTIVE and user's wallet is credited.
- [ ] `python seed.py --reset && python seed.py --verify` shows all tables populated.

---

## README.md OUTLINE (write after all features are done)

```markdown
# PRP Bank

A full-stack demo banking platform built with Flask, Neon Postgres, and vanilla JS.

## Features
- Retail: Deposit / Withdraw / UPI / NEFT / SWIFT / Cheques / Self-transfer
- Cards: Issue Debit/Credit (Visa, Mastercard, RuPay), Block, Activate, Delete
- Loans: EMI-based loans with admin approval workflow
- Investments: Fixed Deposits, Bonds, Mutual Funds, Stocks
- Bills: Pay bills with confirmation modal and real balance deduction
- PFM: Budgets and savings goals
- Admin: User management, approvals queue, audit log, feature flags, config, FX rates, stocks

## Tech Stack
Python 3.11 · Flask 3 · psycopg2 · Neon Postgres · Jinja2 · Vanilla CSS/JS · Gunicorn

## Development Journey
We started as a CLI app → integrated Supabase → hit ISP blocks in India → migrated to Neon DB → wrapped functions as Flask routes → built the Jinja2 frontend.

## Getting Started
1. git clone <repo> && cd prpbankproject
2. pip install -r requirements.txt
3. Copy .env.example → .env and set DATABASE_URL + SECRET_KEY
4. python seed.py --reset
5. flask run → open http://localhost:5000

## Demo Credentials
| Name     | Role  | Password   |
|----------|-------|------------|
| Kahaan   | USER  | B023B023   |
| Zaid     | ADMIN | B024B024   |
| Nishad   | USER  | B025B025   |
| Siddhesh | USER  | PRP01PRP01 |

## Team Contributions
_To be filled in_

## Demo Video
_Link to be added_
```
