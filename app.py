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
        ''')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Error: {e}")
        print("Please check if your Supabase project is active and your URL is correct.")
        exit()


# A simple container to hold the logged-in user's details
class User:
    def __init__(self, name, password, user_id=None, balance=0):
        self.name = name
        self.id = user_id
        self.balance = float(balance)
        self.password = password
    
    def display(self):
        print("Name:", self.name)
        print("ID:", self.id)
        print("Balance:", self.balance)


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
            return User(user_data[1], user_data[3], user_data[0], user_data[2])
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
            "INSERT INTO users (name, password) VALUES (%s, %s)",
            (n, p)
        )

        conn.commit()
        conn.close()
        
        print("\nAccount created successfully!\n")
    except Exception as e:
        print(f"Account Creation Error: {e}")


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
        print("8. Logout")

        try:
            choice = int(input("Enter your choice: "))

            if choice == 1:
                print(f"Current Balance: ₹{user.balance}")

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
                print("Logging out...")
                break
            else:
                print("Invalid choice")
        except ValueError:
            print("Enter a valid number!")
        except Exception as e:
            print("Error:", e)

# The very first screen the user sees when they boot up the app
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