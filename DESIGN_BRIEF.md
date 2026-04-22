# PRP Bank — Design Brief


## Role

You are a senior product designer at a top-tier fintech studio. You are designing a consumer + business retail banking web application from scratch. Your work will be handed to engineering as the source of truth, so define tokens, components, layouts, and every page in both dark and light themes at both desktop and mobile widths.

## Product

**PRP Bank** — a modern retail banking web app for Indian consumers and small-business owners, with a separate admin surface for internal bank operators. The demo must feel like a real bank: institutional, trustworthy, quietly modern. Think Stripe × Revolut × Mercury × Jupiter × Neon. Not a toy, not a fintech MVP.

## Audience (three distinct postures)

1. **Retail customer (18–65)** — everyday banking, UPI, bills, cards, goals, budgets, occasional loans, occasional investments.
2. **Small-business owner** — higher volumes, multiple cards, vendor transfers (NEFT / RTGS / international), invoices.
3. **Bank operator (admin)** — visibly distinct shell, different accent color, approval queues, config, audit, user management, feature flags.

## Design language

Enterprise-grade. Institutional. Trustworthy. Quietly modern.

- **Avoid:** skeuomorphic card art, heavy gradients, neumorphism, glassmorphism, "web3" aesthetics, emoji-first UI, illustrated mascots, crypto-exchange vibes.
- **Favor:** confident typography, generous whitespace, restrained color, subtle depth, deliberate motion, tabular numerics, precise alignment.

## Token system (define these explicitly)

### Color

Define a neutral surface scale from 0 to 900 (11 steps). A single primary (suggest deep ink-blue or indigo `#1e3a8a` / `#4338ca` family). Semantic colors for success, warning, danger, info. A separate **admin accent** (suggest deep violet or bronze) so admin screens feel different from customer screens without being jarring.

Produce full **dark** and **light** themes, both with equivalent contrast. Default to system preference. Every color referenced by token, never raw hex in components.

### Typography

- Primary sans: **Inter** or **Geist Sans**. Weights 400, 500, 600, 700.
- Mono for amounts: **JetBrains Mono**, **Geist Mono**, or **IBM Plex Mono** with tabular figures enabled.
- Type scale (6 steps): display 32, h1 24, h2 20, body 14, caption 12, micro 11. Line heights 1.2 / 1.3 / 1.4 / 1.5 / 1.5 / 1.4.
- Numeric amounts always in mono with tabular figures, so columns align.

### Spacing

8-point grid with 4-point half-steps. Tokens: `space-0.5` (2), `1` (4), `2` (8), `3` (12), `4` (16), `5` (20), `6` (24), `8` (32), `10` (40), `12` (48), `16` (64).

### Radii

Three steps: `radius-sm` (6), `radius-md` (10), `radius-lg` (16). Pills use `radius-full`.

### Elevation

Four shadow levels, used sparingly:
- `elev-0` — flush, no shadow.
- `elev-1` — subtle card lift.
- `elev-2` — dropdown / popover.
- `elev-3` — modal / command palette.

### Motion

- Default transition: 150ms ease-out.
- Surface transitions (drawers, modals): 250ms ease-out.
- No spring bounces. Respect `prefers-reduced-motion` everywhere.

## Layout system

- Breakpoints: **360 / 768 / 1024 / 1440**.
- **Sidebar navigation** (customer): persistent at ≥1024px, collapsible to an icon-rail at 768–1024px, becomes a **bottom-nav** on mobile. Sidebar sections are grouped (Banking, Money, Wealth, Account).
- **Top bar** (persistent, all widths):
  - Left: product mark + current section title.
  - Center: a command-palette trigger (`⌘K`) with global search.
  - Right: balance-at-a-glance chip (can be masked), account switcher (personal/business), notifications bell with unread dot, profile menu.
- **Admin shell** — same skeleton but with a different accent color on the sidebar rail, an "Admin" chip next to the product mark in the topbar, and an audit-log quick-peek in the top-right.
- **Density:** comfortable by default, with an optional compact density toggle in settings.

## Pages to design (customer)

### 1. Login

- Clean centered card, product mark above, one-line value prop.
- Inputs: **username**, **password** with a show/hide toggle and Caps-Lock hint.
- Below the password field: a secondary button **"Use demo credentials"** that opens a dropdown listing seeded personas with a one-line descriptor each. Example rows:
  - `alice` — Everyday customer
  - `bob` — Loan-heavy, with an overdue bill
  - `carol` — Investor, large portfolio
  - `dev` — New user (empty states)
  - `eve` — Counterparty (receives cheques)
  - `admin` — Bank operator (admin panel)
- Selecting a persona autofills both fields and focuses the submit button.
- Secondary links: "Forgot password?", "Create account".
- Error state styled inline under the offending field. No top banners.

### 2. Register

- Stepped layout (3 steps with a progress indicator):
  1. **Identity** — full name, DOB, email, phone (with OTP-style UX readback but no real OTP).
  2. **Credentials** — username, password, confirm password, password-strength meter.
  3. **Review & accept** — summary + T&C checkbox + submit.
- Every field has inline validation and an error state.

### 3. Dashboard

- Greeting with the user's first name + last-login stamp.
- Four KPI tiles: **Wallet**, **Savings**, **Investments**, **Net Worth**. Net Worth nets out active-loan principal and pending bills; show a tooltip explaining the calculation.
- **30-day balance sparkline** across the full width of the KPI row.
- **Spending by category** donut (last 30 days) + legend.
- **"Needs your attention"** strip with dismissable cards: overdue bills, pending cheques to approve, pending admin approvals, near-limit budgets.
- **Recent transactions** list (5 items) with a "view all" link.
- **Quick actions** row: Send money, Pay bill, Add money, Apply for loan.

### 4. Transactions

- Full history, paginated server-side, with:
  - Date-range picker, type filter (credit/debit/both), channel filter (UPI/NEFT/Card/…), amount range slider, free-text search.
  - Columns: Date, Description, Category, Channel, Reference ID, Amount (credit green, debit neutral), Running balance.
  - Sticky day-group headers.
  - CSV export button.
  - Click a row → side drawer with full detail and a "view counterparty" link.

### 5. Deposit / Withdraw

- Single-amount field with large mono numerals.
- **Quick-amount chips**: ₹500 / ₹1,000 / ₹5,000 / ₹10,000 / ₹25,000.
- **Channel selector**: Deposit → Cash / Cheque / Online. Withdraw → ATM / Branch / Online.
- Fee preview (zero for most, shown anyway for transparency).
- **Review step** for any amount above an admin-configurable threshold — shows amount, channel, fee, timestamp, a reference ID placeholder, and a confirm button.
- Success screen with reference ID, "add to notes" chip, and "do another" shortcut.

### 6. Transfers hub

Five lanes as tabs or a segmented control. The first (Self) opens by default.

- **Self** — wallet ⇄ savings, with a single amount field and a direction toggle.
- **Intra-bank** — pay by **account number or username**. Server-side name-readback: after entering the recipient, show "Sending to: Alice Sharma — A/C ending 4321" before the user can confirm.
- **UPI** — UPI ID field with a format hint, QR scan stub (just a button).
- **International** — currency dropdown (USD/EUR/GBP/AED, admin-configurable), live-looking FX rate from the config, transparent fee breakdown (flat + spread), final INR shown.
- **Cheques** — two sub-modes: **Issue** (recipient name + amount, funds are held with a visible "₹X on hold" chip on the dashboard) and **Pending cheques** (cheques issued to you, with Approve / Reject actions).
- High-value transfers (above threshold) show a **"Pending admin approval"** badge on the transfer after submit, and the funds are held but not yet moved.

### 7. Loans

- **Apply** form: principal, tenure (months), purpose. Live EMI preview, total interest, schedule preview.
- **Existing loans** list: principal, balance, EMI, next due date, status chip (Pending / Approved / Active / Overdue / Cleared / Rejected / Defaulted).
- Loan detail page: amortization schedule (table + small bar chart), pay EMI / pay custom / pay full, early-payoff savings estimate.
- Empty state with CTA and a two-sentence explainer.

### 8. Bills

- **Biller catalog** as a grid of icon tiles: Electricity, Mobile, DTH, Internet, Rent, Insurance, Gas, Credit Card. Each tile has an "Add biller" or "Pay now" CTA.
- **Consumer ID** field saved per biller.
- **Auto-pay** toggle per bill.
- **Upcoming bills** strip (next 7 days) with due-day chips.
- **Overdue** bills flagged in danger color.

### 9. Cards

- **Card gallery** (horizontal scroller on mobile, grid on desktop) with realistic Visa / Mastercard / RuPay art. Each card shows cardholder name, last-4, network, type (Debit / Credit / Virtual), status chip.
- Per-card detail: block / unblock / renew / set PIN / set daily limit / set international toggle / view transactions filtered to this card.
- "Add new card" flow asks for type, network preference, and linked funding source.

### 10. Investments

- **Portfolio KPIs**: Invested, Current value, Absolute P&L (₹), Percentage P&L.
- **Asset allocation donut** (FD / Bonds / MF / Equity).
- **Safe instruments** list with maturity date, accrual-to-date, redeem action.
- **Equity holdings** table with symbol, qty, avg buy, current price, day-change, current value, P&L. Sell button opens a confirm modal.
- **Watchlist** separate from holdings.
- "Simulate tick" text hint explaining that prices update periodically (the admin controls this).

### 11. PFM (Personal Finance)

- **Goals** — card grid, each goal with a progress ring, saved/target amounts, deadline, contribute action, mark-complete.
- **Budgets** — category rows with actual-vs-limit bars, color-states (ok → near → over), monthly reset timestamp. A budget detail drawer lists the transactions that count toward it.
- **Spending analytics** — income vs expense bar chart (last 6 months) + category pie.

### 12. Profile / Settings

- Tabs: Personal info, KYC, Security, Notifications, Appearance.
- KYC shows status and a "request upgrade" button (creates an admin approval item).
- Security: change password, enable 2FA stub, active sessions list with "revoke" per session.
- Appearance: theme toggle (System / Light / Dark), density toggle.

## Pages to design (admin)

Visually distinct: admin accent color on the sidebar rail, an "Admin" chip in the topbar, audit-log peek in top-right.

### 13. Admin dashboard

KPI tiles: total users / active / frozen / KYC pending, deposits today, loans outstanding, pending approvals, failed transactions (24h), system status. Below: a live activity feed and a "recent admin actions" stream.

### 14. Users

- Searchable, filterable table (role, status, KYC, created date).
- Row actions: View, Freeze, Unfreeze, Credit, Reset password, Close.
- **User detail drawer** (or full page) with: profile, balance history chart, all cards, all loans, recent activity, audit trail for this user.

### 15. Config

- Editable **key-value board** grouped by domain:
  - **Rates**: loan interest %, FD %, Bonds %, MF %, savings interest %.
  - **Fees**: NEFT fee, international flat fee, international spread %, ATM fee.
  - **Limits**: daily withdraw, single transfer, high-value approval threshold, international per-day.
  - **Windows**: bill due days, cheque clearing days, loan grace period days.
  - **Features**: toggle every customer flow on/off (enable_international_transfers, enable_cheques, enable_stocks, enable_loans, require_loan_approval, require_high_value_approval, demo_mode, …).
- Each field shows: current value, last-updated-by, last-updated-at, and an inline edit with a confirm.

### 16. Approval queue

Tabs for **Loans**, **Cheques**, **High-value transfers**, **KYC upgrades**. Each row: requester (with link to user detail), amount, reason, timestamp, approve / reject. Reject requires a reason (textarea, min 10 chars).

### 17. FX rates

Editable per currency pair table (base, quote, rate, last-updated). History timeline per pair.

### 18. Stocks

Editable instrument list (symbol, name, price). A prominent **"Simulate tick"** button that nudges every price ±2% and updates holdings valuations. Show a mini sparkline per row.

### 19. Seed & reset

- **Reseed demo data** (confirmation modal with checklist of what gets replaced).
- **Reset single user** (pick a user, resets balance + transactions).
- **Generate N synthetic transactions** for a user (slider 10–500).
- Every action has a dry-run preview.

### 20. Audit log

Paginated log with filters: admin, action, target type, date. Each row expandable to show before / after JSON diff.

## Cross-cutting components (design these explicitly)

- **Empty states** with a small illustration, a one-line explainer, and a primary CTA. Design one per major page (no transactions, no bills, no cards, no goals, no investments).
- **Skeleton loaders** matching the shape of every list, table, and card.
- **Toast notifications** (bottom-right) replacing any top-of-page banner pattern. Variants: success, warning, danger, info. Auto-dismiss 4s, hover to pause, `×` to close.
- **Confirmation modals** for destructive / high-value actions. Double-confirm for amounts above threshold.
- **Inline form error states** under each field (not only top-of-page).
- **Command palette (`⌘K`)** with: jump to page, jump to user (admin), quick actions (Send money, Pay bill, Add card), recent transactions search.
- **Notification drawer** (from right) with grouped notifications.
- **Balance mask toggle** — click the balance chip to mask all money numbers behind dots.
- **Keyboard shortcuts overlay** (`?` to open).

## Accessibility

- WCAG 2.2 **AA** minimum. Aim for AAA on text contrast where possible.
- Focus-visible rings on every interactive element.
- ARIA labels on icon-only buttons.
- Status is never color-alone (always paired with an icon or label).
- Keyboard navigation across every flow, with a visible "skip to main" link.
- Screen-reader-friendly amount labels (e.g. `aria-label="One thousand rupees"` on tabular numerals).
- Respect `prefers-reduced-motion`, `prefers-color-scheme`, and `prefers-contrast`.

## Brand + tone

- **Product name:** PRP Bank.
- **Currency:** Indian Rupees, formatted in the Indian numbering system (lakhs / crores) with ₹ prefix.
- **Vocabulary:** UPI, NEFT, RTGS, IFSC, KYC, PAN, EMI, NAV — these are native terms, use them directly.
- **Voice:** concise, factual, confident. Short sentences. No exclamation marks. No "Oops!" errors — just plain language: "Something went wrong. Reference: PRP-1A2B3C."
- **Dates:** "21 Apr 2026, 14:02". **Times:** 24-hour.

## Deliverables

1. A complete **Figma-style component system** covering every token and primitive.
2. **Every page listed above**, in both dark and light themes, at **1440px** and **375px** widths.
3. **Admin shell** variants for pages 13–20.
4. Component states: default, hover, focus, active, disabled, loading, error.
5. A **principles one-pager** summarizing voice, motion, density, and density toggle behavior.

## Out of scope

- No marketing / landing pages.
- No onboarding animation sequences beyond 150ms transitions.
- No illustration system beyond empty-state sketches.
- No custom icon family — use Lucide or Heroicons by reference; do not redraw.
- No native mobile app designs (mobile web only).

---

**When you are done, return a single design hand-off package with all tokens, components, and high-fidelity mocks as described. Flag any decisions you deviated from and why.**
