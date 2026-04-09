import os
import psycopg2
from dotenv import load_dotenv

# Grab the database connection string from our hidden .env file
load_dotenv()
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("Error: DATABASE_URL not found. Check your .env file.")
    exit()

# Make sure our database has the right tables ready to go before the app starts
def db_init():
    try:
        conn = psycopg2.connect(db_url, sslmode='require')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                balance NUMERIC DEFAULT 0,
                password TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(50) NOT NULL,
                amount NUMERIC NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS loans (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                principal NUMERIC NOT NULL,
                interest_rate NUMERIC DEFAULT 5.0,
                total_owed NUMERIC NOT NULL,
                amount_paid NUMERIC DEFAULT 0,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS bills (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                bill_type VARCHAR(50),
                amount NUMERIC,
                status VARCHAR(20) DEFAULT 'PAID',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                target_amount NUMERIC NOT NULL,
                current_amount NUMERIC DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                limit_amount NUMERIC NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transfers (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                receiver_info TEXT,
                amount NUMERIC,
                type VARCHAR(30),
                status VARCHAR(20) DEFAULT 'COMPLETED',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cheques (
                id SERIAL PRIMARY KEY,
                issuer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                receiver_name TEXT,
                amount NUMERIC,
                status VARCHAR(20) DEFAULT 'PENDING',
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Ensure savings_balance exists
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='savings_balance') THEN
                    ALTER TABLE users ADD COLUMN savings_balance NUMERIC DEFAULT 0;
                END IF;
            END $$;
        ''')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Error: {e}")
        print("Please check if your Supabase project is active and your URL is correct.")
        exit()


class User:
    def __init__(self, name, password, user_id=None, balance=0, savings_balance=0):
        self.name = name
        self.id = user_id
        self.balance = float(balance)
        self.savings_balance = float(savings_balance or 0)
        self.password = password
    
    def display(self):
        print("Name:", self.name)
        print("ID:", self.id)
        print("Wallet Balance: ₹", self.balance)
        print("Savings Balance: ₹", self.savings_balance)


def login():
    name = input("Enter Username: ").strip()
    passw = input("Enter Password: ").strip()
    
    try:
        conn = psycopg2.connect(db_url, sslmode='require')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE name=%s AND password=%s",
            (name, passw)
        )

        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            savings = user_data[4] if len(user_data) > 4 else 0
            user = User(user_data[1], user_data[3], user_data[0], user_data[2], savings)
            print("\nLogin Successful!")
            return user
        else:
            print("\nInvalid Credentials!")
            return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None


def createAccount():
    n = input("Enter Name: ").strip()
    p = input("Enter Password: ").strip()
    
    try:
        conn = psycopg2.connect(db_url, sslmode='require')
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (name, password, savings_balance) VALUES (%s, %s, 0)",
            (n, p)
        )

        conn.commit()
        conn.close()
        
        print("\nAccount created successfully!\n")
    except Exception as e:
        print(f"Account Creation Error: {e}")


def transfersMenu(user):
    while True:
        print("\n--- TRANSFERS ---")
        print("1. Self Transfer")
        print("2. Other Bank Transfer")
        print("3. UPI Transfer")
        print("4. International Transaction")
        print("5. NEFT Transfer")
        print("6. Cheque Approval")
        print("7. Back")

        try:
            choice = int(input("Choice: "))

            if choice == 1:
                print(f"Wallet: ₹{user.balance} | Savings: ₹{user.savings_balance}")
                print("1. Wallet → Savings\n2. Savings → Wallet")
                direction = int(input("Choice: "))
                amt = float(input("Amount: ₹"))

                if direction == 1:
                    if amt <= 0 or amt > user.balance:
                        print("Invalid amount.")
                    else:
                        user.balance -= amt
                        user.savings_balance += amt
                        conn = psycopg2.connect(db_url, sslmode='require')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET balance=%s, savings_balance=%s WHERE id=%s", (user.balance, user.savings_balance, user.id))
                        cursor.execute("INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,%s)", (user.id, "SELF-SAVINGS", amt, "SELF"))
                        conn.commit()
                        conn.close()
                        print("Transferred to savings!")
                elif direction == 2:
                    if amt <= 0 or amt > user.savings_balance:
                        print("Invalid amount.")
                    else:
                        user.savings_balance -= amt
                        user.balance += amt
                        conn = psycopg2.connect(db_url, sslmode='require')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET balance=%s, savings_balance=%s WHERE id=%s", (user.balance, user.savings_balance, user.id))
                        cursor.execute("INSERT INTO transfers (sender_id, receiver_info, amount, type) VALUES (%s,%s,%s,%s)", (user.id, "SELF-WALLET", amt, "SELF"))
                        conn.commit()
                        conn.close()
                        print("Transferred to wallet!")

            elif choice == 2:
                pass

            elif choice == 3:
                pass

            elif choice == 4:
                pass

            elif choice == 5:
                pass

            elif choice == 6:
                pass

            elif choice == 7:
                break

        except Exception as e:
            print("Error:", e)


def pfmMenu(user):
    while True:
        print("\n--- PERSONAL FINANCE MANAGEMENT ---")
        print("1. Set Financial Goal")
        print("2. Add to Goal")
        print("3. Set Budget Limit")
        print("4. View Savings Status & Insights")
        print("5. Back to Dashboard")

        try:
            choice = int(input("Choice: "))
            if choice == 1:
                name = input("Goal Name: ")
                target = float(input("Target Amount: ₹"))
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO goals (user_id, name, target_amount) VALUES (%s, %s, %s)", (user.id, name, target))
                conn.commit()
                conn.close()
                print("Goal set!")

            elif choice == 2:
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, target_amount, current_amount FROM goals WHERE user_id=%s", (user.id,))
                goals = cursor.fetchall()
                if not goals:
                    print("No goals found")
                    conn.close()
                    continue
                for g in goals:
                    print(f"ID: {g[0]} | {g[1]}: ₹{g[3]}/₹{g[2]}")
                gid = int(input("Goal ID: "))
                amt = float(input("Amount to add: ₹"))
                if 0 < amt <= user.balance:
                    user.balance -= amt
                    cursor.execute("UPDATE goals SET current_amount = current_amount + %s WHERE id=%s", (amt, gid))
                    cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, "GOAL_CONTRIBUTION", amt))
                    conn.commit()
                    print("Contributed successfully!")
                else: print("Invalid Amount/Balance")
                conn.close()

            elif choice == 3:
                cat = input("Category (e.g. Food, Travel): ")
                limit = float(input("Monthly Limit: ₹"))
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (%s, %s, %s)", (user.id, cat, limit))
                conn.commit()
                conn.close()
                print("Budget set!")

            elif choice == 4:
                print(f"Wallet Balance: ₹{user.balance}")
                print(f"Savings Account Balance: ₹{user.savings_balance}")
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("SELECT name, target_amount, current_amount FROM goals WHERE user_id=%s", (user.id,))
                for g in cursor.fetchall():
                    progress = (g[2]/g[1])*100 if g[1] > 0 else 0
                    print(f"Goal: {g[0]} - {progress:.1f}% Complete (₹{g[2]} of ₹{g[1]})")
                conn.close()

            elif choice == 5:
                break
        except Exception as e:
            print("Error:", e)


def dashboard(user):
    while True:
        print("\n--- DASHBOARD ---")
        print("1. View Balance")
        print("2. Deposit Money")
        print("3. Withdraw Money")
        print("4. View Transaction History")
        print("5. Apply for a Loan")
        print("6. Repay a Loan")
        print("7. Pay Bills")
        print("8. Personal Finance Management")
        print("9. Logout")

        try:
            choice = int(input("Enter your choice: "))

            if choice == 1:
                print(f"Wallet Balance: ₹{user.balance}")
                print(f"Savings Balance: ₹{user.savings_balance}")

            elif choice == 2:
                amount = float(input("Enter Amount to deposit: "))
                if amount > 0:
                    user.balance += amount
                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, 'DEPOSIT', amount))
                    conn.commit()
                    conn.close()
                    print("Amount deposited successfully!")
                else:
                    print("Invalid Amount")

            elif choice == 3:
                withdraw = float(input("Enter Amount to Withdraw: "))
                if withdraw > user.balance:
                    print("Insufficient balance!")
                elif withdraw > 0:
                    user.balance -= withdraw
                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, 'WITHDRAWAL', withdraw))
                    conn.commit()
                    conn.close()
                    print("Amount withdrawn successfully!")
                else:
                    print("Invalid Amount")

            elif choice == 4:
                print("\n--- TRANSACTION HISTORY ---")
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("SELECT type, amount, timestamp FROM transactions WHERE user_id=%s ORDER BY timestamp DESC", (user.id,))
                history = cursor.fetchall()
                conn.close()

                if not history:
                    print("No transactions found.")
                else:
                    for record in history:
                        print(f"[{record[2]}] {record[0]}: ₹{record[1]}")

            elif choice == 5:
                principal = float(input("Enter loan amount requested: ₹"))
                if principal > 0:
                    interest_rate = 5.0
                    total_owed = principal + (principal * (interest_rate / 100))
                    print(f"You will owe: ₹{total_owed}")
                    confirm = input("Type 'yes' to accept: ").strip().lower()

                    if confirm == 'yes':
                        user.balance += principal
                        conn = psycopg2.connect(db_url, sslmode='require')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                        cursor.execute("INSERT INTO loans (user_id, principal, total_owed) VALUES (%s, %s, %s)", (user.id, principal, total_owed))
                        cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, 'LOAN_DISBURSEMENT', principal))
                        conn.commit()
                        conn.close()
                        print("Loan approved!")
                else:
                    print("Invalid amount.")

            elif choice == 6:
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                cursor.execute("SELECT id, total_owed, amount_paid FROM loans WHERE user_id=%s AND status='ACTIVE'", (user.id,))
                active_loans = cursor.fetchall()

                if not active_loans:
                    print("No active loans!")
                    conn.close()
                    continue

                for loan in active_loans:
                    print(f"Loan ID: {loan[0]} | Remaining: ₹{loan[1] - loan[2]}")

                try:
                    target_loan = int(input("Loan ID: "))
                    pay_amount = float(input("Amount: ₹"))

                    if pay_amount > user.balance:
                        print("Insufficient balance!")
                        conn.close()
                        continue

                    cursor.execute("SELECT total_owed, amount_paid FROM loans WHERE id=%s AND user_id=%s AND status='ACTIVE'", (target_loan, user.id))
                    loan_data = cursor.fetchone()

                    if loan_data:
                        owed, paid = float(loan_data[0]), float(loan_data[1])
                        remaining = owed - paid

                        if pay_amount > remaining:
                            pay_amount = remaining

                        user.balance -= pay_amount
                        new_paid = paid + pay_amount
                        status = 'CLEARED' if new_paid >= owed else 'ACTIVE'

                        cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                        cursor.execute("UPDATE loans SET amount_paid=%s, status=%s WHERE id=%s", (new_paid, status, target_loan))
                        cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, 'LOAN_REPAYMENT', pay_amount))
                        conn.commit()
                        print("Payment successful!")
                except Exception as e:
                    print("Invalid input:", e)
                conn.close()

            elif choice == 7:
                print("\n--- BILL PAYMENT ---")
                print("1. Electricity\n2. Mobile\n3. Water\n4. Rent")
                try:
                    b_choice = int(input("Choice: "))
                    types = {1: "ELECTRICITY", 2: "MOBILE", 3: "WATER", 4: "RENT"}
                    if b_choice in types:
                        amount = float(input("Amount: ₹"))
                        if 0 < amount <= user.balance:
                            user.balance -= amount
                            conn = psycopg2.connect(db_url, sslmode='require')
                            cursor = conn.cursor()
                            cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                            cursor.execute("INSERT INTO bills (user_id, bill_type, amount) VALUES (%s, %s, %s)", (user.id, types[b_choice], amount))
                            cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)", (user.id, 'BILL_PAYMENT', amount))
                            conn.commit()
                            conn.close()
                            print("Bill paid successfully!")
                        else:
                            print("Invalid / Insufficient balance")
                    else:
                        print("Invalid choice")
                except:
                    print("Invalid input")

            elif choice == 8:
                pfmMenu(user)

            elif choice == 9:
                print("Logging out...")
                break
            else:
                print("Invalid choice")
        except ValueError:
            print("Enter a valid number!")
        except Exception as e:
            print("Error:", e)

def loginPage():
    db_init()

    while True:
        print("\n1. Login\n2. Sign Up\n3. Exit")

        try:
            c = int(input("Enter choice: "))

            if c == 1:
                user = login()
                if user:
                    dashboard(user)

            elif c == 2:
                createAccount()

            elif c == 3:
                print("Exiting...")
                break

            else:
                print("Invalid Choice")

        except ValueError:
            print("Enter a valid number!")
        except Exception as e:
            print("Error:", e)


# Kick off the application
if __name__ == "__main__":
    loginPage()