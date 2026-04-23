## **A full-stack demo banking platform deployed on prpproject.madridonomy.com**

---

## 📋 Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Development Journey](#development-journey)
- [Getting Started](#getting-started)
- [Demo Credentials](#demo-credentials)
- [Team Contributions](#team-contributions)
- [Demo Video](#demo-video)

---

## About the Project

**PRP Bank** is a comprehensive internet-banking simulation that covers the full spectrum of retail banking operations — from day-to-day deposits and transfers to EMI-based loans, investment portfolios, bill payments, and a complete admin operations console. The project was built as an end-to-end learning exercise in full-stack development, database design, and real-world problem solving.

Every feature mirrors how a production banking system would behave: loans go through an admin approval queue before funds are disbursed, international transfers pull live FX rates from the database, credit cards track usage against limits, and all high-value operations generate audit trail entries.

---

## Features

### 🏦 Retail Banking

- **Deposit & Withdraw** — Instant wallet balance updates with transaction logging
- **Transfers** — Self-transfer (wallet ↔ savings), Bank-to-bank, UPI, NEFT, IMPS, International (SWIFT), and Cheque issuance with fund holds
- **Transaction History** — Full ledger with category, channel, counterparty, and reference tracking

### 💳 Cards

- Issue **Debit** and **Credit** cards (Visa, Mastercard, RuPay)
- Block, Activate, and Delete cards with click-to-expand management
- Credit utilisation progress bars with colour-coded thresholds

### 🏠 Loans

- **EMI-based loan applications** — Personal, Home, Auto, Education
- Live EMI calculator with type-specific interest rates
- Admin approval workflow — funds credited only after approval

### 📈 Investments

- **Stocks** — Buy/sell with real-time price display
- **Mutual Funds & Bonds** — Portfolio tracking with returns and change percentages
- **Fixed Deposits** — Maturity date tracking

### 📄 Bills & Payments

- Bill management with status tracking (Pending, Overdue, Scheduled, Paid)
- Confirmation modal before payment — no accidental deductions

### 💰 Personal Finance Management

- **Budget tracking** — Category-wise monthly limits vs. actual spend
- **Savings goals** — Target amounts, progress bars, and deadlines

### ⚙️ Admin Operations Console

- **User Management** — View all accounts, tiers, statuses, and balances
- **Approval Queue** — Review and approve/reject loans, transfers, card-limit requests
- **Audit Log** — Timestamped trail of every system action
- **Feature Flags** — Toggle modules (international transfers, investments, cheques, etc.)
- **Configuration** — Runtime config for transfer limits, fees, overdraft charges, loan rates
- **FX Rate Management** — Update currency exchange rates from the admin panel
- **Stock Price Management** — Update stock prices and change percentages

---

## Tech Stack


| Layer          | Technology                                                                  |
| -------------- | --------------------------------------------------------------------------- |
| **Backend**    | Python 3.12 · Flask 3 · Gunicorn                                            |
| **Database**   | Neon PostgreSQL (cloud)                                                     |
| **Templating** | Jinja2                                                                      |
| **Frontend**   | Vanilla HTML, CSS, Javascript with Jinja templating for backend connection. |
| **Auth**       | Werkzeug password hashing (scrypt) · Flask sessions                         |
| **Deployment** | Render, Hostinger                                                           |


---

## Development Journey

This project wasn't built in a straight line — it evolved through real constraints and pivots:

```
   CLI App          Supabase           Neon DB           Flask Routes        Frontend
  ┌─────────┐     ┌───────────┐     ┌────────────┐     ┌──────────────┐    ┌──────────────┐
  │ Modular  │────▶│ Cloud DB  │────▶│ Alternative│────▶│ HTTP API     │───▶│ Jinja2 +     │
  │ Python   │     │ Postgres  │     │ Cloud      │     │ Layer        │    │ Vanilla JS   │
  │ Functions│     │           │     │ Postgres   │     │              │    │              │
  └─────────┘     └───────────┘     └────────────┘     └──────────────┘    └──────────────┘
       │                │                 │                   │                   │
  Started with     Integrated         Supabase got       Wrapped each        Connected the
  a terminal-      Supabase for       blocked by some    CLI function        backend to a
  based banking    persistent         ISPs in India,     into a Flask        full Jinja2
  app — each       data storage       so we migrated     route with         frontend with
  feature as a     and auth           to Neon DB, a      proper request     responsive
  standalone                          free cloud         handling and       layouts, tab
  function                            PostgreSQL         session mgmt       navigation,
                                      provider                              and modals
```

> **Key takeaway:** Building modular, function-first code from day one made every migration painless. When Supabase got blocked, swapping to Neon was a config change. When we moved from CLI to web, each function became a route without rewriting business logic.

---

## Getting Started

🔗 **Live Deployed Application:** ([https://prpproject.madridonomy.com](https://prpproject.madridonomy.com))

### Prerequisites

- Python 3.10+ (3.12 recommended)
- A [Neon](https://neon.tech) PostgreSQL database (free tier works)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd prpbankproject

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
Create a .env file and paste the following :

DATABASE_URL=postgresql://neondb_owner:npg_DxyuoMg7cGN1@ep-gentle-cake-a1s7y552.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

# 4. Run the application
python app.py
```

## Demo Credentials - For Demonstration Convinience, you can click and autofill credentials on the login page on [prpproject.madridonomy.com](http://prpproject.madridonomy.com) 


| Name         | Role    | Password     | Branch                |
| ------------ | ------- | ------------ | --------------------- |
| **Kahaan**   | `USER`  | `B023B023`   | Mumbai — Bandra West  |
| **Zaid**     | `ADMIN` | `B024B024`   | Mumbai — Bandra West  |
| **Nishad**   | `USER`  | `B025B025`   | Mumbai — Andheri East |
| **Siddhesh** | `USER`  | `PRP01PRP01` | Mumbai — Thane West   |


> Log in as **Zaid** to access the Admin Operations Console (approvals, audit log, feature flags, etc.)

---

## Team Contributions


| Member     | Contributions                                                                                                                                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Kahaan** | Worked on Transfers (NEFT, UPI,International,etc), Personal FInance Management and the bank admin side. Did database integration and frontend mapping for all features built on the CLI application using flask and jinja2 templating. |
| **Zaid**   | Worked on User Registration and Login, Deposit and Withdrawal of funds, Payments of Bills and Investments (stocks, mutual funds, savings).                                                                                             |
| **Nishad** | Worked on the main Account Dashboard for users, Transaction History, Loan management and application and card management.                                                                                                              |


---

## Demo Video

> 🎬 *Video link to be added*

---

