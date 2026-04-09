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

            CREATE TABLE IF NOT EXISTS cards (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                card_number TEXT UNIQUE,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                expiry_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
                       
            CREATE TABLE IF NOT EXISTS investments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(20),
                amount NUMERIC,
                returns NUMERIC DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
                       
            CREATE TABLE IF NOT EXISTS bills (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                bill_type TEXT,
                amount NUMERIC,
                due_date DATE,
                status TEXT DEFAULT 'PENDING'
            );
        ''')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Error: {e}")
        print("Please check if your Supabase project is active and your URL is correct.")
        exit()


# A simple container to hold the logged-in user's details so we can pass them around easily
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

        # If we found a match, create a User object so the app remembers who is logged in
        if user_data:
            user = User(user_data[1], user_data[3], user_data[0], user_data[2])
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
            "INSERT INTO users (name, password) VALUES (%s, %s)",
            (n, p)
        )

        conn.commit()
        conn.close()
        
        print("\nAccount created successfully!\n")
    except Exception as e:
        print(f"Account Creation Error: {e}")


# The main menu where logged-in users can manage their money
def dashboard(user):
    while True:
        print("\n--- DASHBOARD ---")
        print("1. View Balance")
        print("2. Deposit Money")
        print("3. Withdraw Money")
        print("4. View Transaction History")
        print("5. Apply for a Loan")       # NEW
        print("6. Repay a Loan")           # NEW
        print("7. Pay Bills")   # NEW
        print("8. Card Management")
        print("9. Investments")
        print("10. Logout")

        try:
            choice = int(input("Enter your choice: "))

            if choice == 1:
                print("Current Balance:", user.balance)

            elif choice == 2:
                amount = float(input("Enter Amount to deposit: "))
                if amount > 0:
                    user.balance += amount

                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()

                    # Update their main balance first
                    cursor.execute(
                        "UPDATE users SET balance=%s WHERE id=%s",
                        (user.balance, user.id)
                    )

                    # Keep a receipt of this action in our history table
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)",
                        (user.id, 'DEPOSIT', amount)
                    )

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

                    # Update their main balance first
                    cursor.execute(
                        "UPDATE users SET balance=%s WHERE id=%s",
                        (user.balance, user.id)
                    )

                    # Keep a receipt of this action in our history table
                    cursor.execute(
                        "INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)",
                        (user.id, 'WITHDRAWAL', withdraw)
                    )

                    conn.commit()
                    conn.close()

                    print("Amount withdrawn successfully!")
                else:
                    print("Invalid Amount")

            elif choice == 4:
                print("\n--- TRANSACTION HISTORY ---")
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()

                # Grab all transactions for this user and sort them so the newest show up first
                cursor.execute(
                    "SELECT type, amount, timestamp FROM transactions WHERE user_id=%s ORDER BY timestamp DESC",
                    (user.id,)
                )
                
                history = cursor.fetchall()
                conn.close()

                if not history:
                    print("No transactions found.")
                else:
                    for record in history:
                        t_type = record[0]
                        t_amount = record[1]
                        t_time = record[2]
                        print(f"[{t_time}] {t_type}: ₹{t_amount}")
            
            elif choice == 5:
                principal = float(input("Enter loan amount requested: ₹"))
                if principal > 0:
                    interest_rate = 5.0  # Flat 5% interest
                    total_owed = principal + (principal * (interest_rate / 100))
                    
                    print(f"Bank Offer: {interest_rate}% interest rate.")
                    print(f"You will owe a total of: ₹{total_owed}")
                    confirm = input("Type 'yes' to accept: ").strip().lower()
                    
                    if confirm == 'yes':
                        # 1. Give them the money
                        user.balance += principal
                        
                        conn = psycopg2.connect(db_url, sslmode='require')
                        cursor = conn.cursor()
                        
                        # 2. Update their wallet balance
                        cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                        
                        # 3. Create the loan record
                        cursor.execute(
                            "INSERT INTO loans (user_id, principal, total_owed) VALUES (%s, %s, %s)",
                            (user.id, principal, total_owed)
                        )
                        
                        # 4. Log the transaction
                        cursor.execute(
                            "INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)",
                            (user.id, 'LOAN_DISBURSEMENT', principal)
                        )
                        
                        conn.commit()
                        conn.close()
                        print("\nLoan approved! Money has been added to your balance.")
                    else:
                        print("\nLoan cancelled.")
                else:
                    print("Invalid amount.")
            
            elif choice == 6:
                conn = psycopg2.connect(db_url, sslmode='require')
                cursor = conn.cursor()
                
                # Find all active loans for this user
                cursor.execute("SELECT id, total_owed, amount_paid FROM loans WHERE user_id=%s AND status='ACTIVE'", (user.id,))
                active_loans = cursor.fetchall()
                
                if not active_loans:
                    print("\nYou do not have any active loans!")
                    conn.close()
                    continue
                
                print("\n--- YOUR ACTIVE LOANS ---")
                for loan in active_loans:
                    l_id = loan[0]
                    l_owed = loan[1]
                    l_paid = loan[2]
                    l_remaining = l_owed - l_paid
                    print(f"Loan ID: {l_id} | Total Owed: ₹{l_owed} | Remaining Balance: ₹{l_remaining}")
                
                try:
                    target_loan = int(input("\nEnter the Loan ID you want to pay towards: "))
                    pay_amount = float(input("Enter amount to pay: ₹"))
                    
                    if pay_amount > user.balance:
                        print("Insufficient balance in your wallet to make this payment!")
                    elif pay_amount > 0:
                        # Verify the loan belongs to them and is active
                        cursor.execute("SELECT total_owed, amount_paid FROM loans WHERE id=%s AND user_id=%s AND status='ACTIVE'", (target_loan, user.id))
                        loan_data = cursor.fetchone()
                        
                        if loan_data:
                            owed = float(loan_data[0])
                            paid = float(loan_data[1])
                            remaining = owed - paid
                            
                            # Prevent overpaying
                            if pay_amount > remaining:
                                print(f"You only owe ₹{remaining}.")
                                pay_amount = remaining
                                
                            # 1. Deduct from wallet
                            user.balance -= pay_amount
                            cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                            
                            # 2. Update loan paid amount
                            new_paid_total = paid + pay_amount
                            new_status = 'CLEARED' if new_paid_total >= owed else 'ACTIVE'
                            
                            cursor.execute(
                                "UPDATE loans SET amount_paid=%s, status=%s WHERE id=%s",
                                (new_paid_total, new_status, target_loan)
                            )
                            
                            # 3. Log the transaction
                            cursor.execute(
                                "INSERT INTO transactions (user_id, type, amount) VALUES (%s, %s, %s)",
                                (user.id, 'LOAN_REPAYMENT', pay_amount)
                            )
                            
                            conn.commit()
                            print(f"\nPayment of ₹{pay_amount} successful!")
                            if new_status == 'CLEARED':
                                print("Congratulations! This loan has been fully paid off.")
                        else:
                            print("Invalid Loan ID.")
                    else:
                        print("Invalid amount.")
                except ValueError:
                    print("Please enter valid numbers.")
                    
                conn.close()
        
            elif choice == 7:
                print("\n--- BILL SYSTEM ---")
                print("1. Add Bill")
                print("2. View Pending Bills")
                print("3. Pay Bill")

                try:
                    b_choice = int(input("Enter choice: "))
                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()

                    if b_choice == 1:
                        b_type = input("Enter bill type: ").upper()
                        amount = float(input("Enter amount: ₹"))

                        cursor.execute(
                            "INSERT INTO bills (user_id, bill_type, amount, due_date) VALUES (%s,%s,%s,CURRENT_DATE + INTERVAL '7 days')",
                            (user.id, b_type, amount)
                        )
                        conn.commit()
                        print("Bill added!")

                    elif b_choice == 2:
                        cursor.execute(
                            "SELECT id, bill_type, amount, due_date FROM bills WHERE user_id=%s AND status='PENDING'",
                            (user.id,)
                        )
                        bills = cursor.fetchall()

                        if not bills:
                            print("No pending bills.")
                        else:
                            for b in bills:
                                print(f"ID:{b[0]} | {b[1]} | ₹{b[2]} | Due:{b[3]}")

                    elif b_choice == 3:
                        bill_id = int(input("Enter Bill ID: "))

                        cursor.execute(
                            "SELECT amount FROM bills WHERE id=%s AND user_id=%s AND status='PENDING'",
                            (bill_id, user.id)
                        )
                        bill = cursor.fetchone()

                        if not bill:
                            print("Invalid bill.")
                        else:
                            amount = float(bill[0])
                            if amount > user.balance:
                                print("Insufficient balance!")
                            else:
                                user.balance -= amount

                                cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                                cursor.execute("UPDATE bills SET status='PAID' WHERE id=%s", (bill_id,))

                                cursor.execute(
                                    "INSERT INTO transactions (user_id, type, amount) VALUES (%s,%s,%s)",
                                    (user.id, 'BILL_PAYMENT', amount)
                                )

                                conn.commit()
                                print("Bill paid successfully!")

                    conn.close()

                except Exception as e:
                    print("Error:", e)
            elif choice == 8:
                print("\n--- CARD MANAGEMENT ---")
                print("1. Add Card")
                print("2. Block Card")
                print("3. Renew Card")
                print("4. View Cards")

                try:
                    c_choice = int(input("Enter choice: "))
                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()

                    if c_choice == 1:
                        import random
                        card_number = str(random.randint(1000000000000000, 9999999999999999))
                        expiry = "2030-12-31"

                        cursor.execute(
                            "INSERT INTO cards (user_id, card_number, expiry_date) VALUES (%s, %s, %s)",
                            (user.id, card_number, expiry)
                        )
                        conn.commit()
                        print(f"Card Added! Number: {card_number}")

                    elif c_choice == 2:
                        card_id = int(input("Enter Card ID to block: "))
                        cursor.execute(
                            "UPDATE cards SET status='BLOCKED' WHERE id=%s AND user_id=%s",
                            (card_id, user.id)
                        )
                        conn.commit()
                        print("Card Blocked.")

                    elif c_choice == 3:
                        card_id = int(input("Enter Card ID to renew: "))
                        cursor.execute(
                            "UPDATE cards SET expiry_date='2035-12-31', status='ACTIVE' WHERE id=%s AND user_id=%s",
                            (card_id, user.id)
                        )
                        conn.commit()
                        print("Card Renewed.")

                    elif c_choice == 4:
                        cursor.execute(
                            "SELECT id, card_number, status, expiry_date FROM cards WHERE user_id=%s",
                            (user.id,)
                        )
                        cards = cursor.fetchall()

                        if not cards:
                            print("No cards found.")
                        else:
                            for c in cards:
                                print(f"ID: {c[0]} | Number: {c[1]} | Status: {c[2]} | Expiry: {c[3]}")

                    else:
                        print("Invalid choice.")

                    conn.close()

                except Exception as e:
                    print("Error:", e)

            elif choice == 9:
                print("\n--- INVESTMENTS ---")
                print("1. Safe Investments")
                print("2. Risky Stocks")
                print("3. View Investments")

                try:
                    i_choice = int(input("Enter choice: "))
                    conn = psycopg2.connect(db_url, sslmode='require')
                    cursor = conn.cursor()

                    if i_choice == 1:
                        print("1. Fixed Deposit (5%)")
                        print("2. Bonds (7%)")
                        print("3. Mutual Fund (10%)")

                        s_choice = int(input("Select type: "))
                        amount = float(input("Enter amount: ₹"))

                        rates = {1:0.05, 2:0.07, 3:0.10}
                        names = {1:"FD", 2:"BONDS", 3:"MF"}

                        if s_choice in rates and amount <= user.balance:
                            user.balance -= amount
                            returns = amount * rates[s_choice]

                            cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))
                            cursor.execute(
                                "INSERT INTO investments (user_id,type,amount,returns) VALUES (%s,%s,%s,%s)",
                                (user.id, names[s_choice], amount, returns)
                            )
                            conn.commit()
                            print(f"Invested! Expected return: ₹{returns}")
                        else:
                            print("Invalid.")

                    elif i_choice == 2:
                        print("\n--- STOCK OPTIONS ---")
                        stocks = {
                            1: ("TechCorp", 100),
                            2: ("GreenEnergy", 200),
                            3: ("FinBank", 150)
                        }

                        for k,v in stocks.items():
                            print(f"{k}. {v[0]} | Current Price: ₹{v[1]}")

                        s = int(input("Choose stock: "))
                        qty = int(input("Quantity: "))

                        if s in stocks:
                            name, price = stocks[s]
                            total = price * qty

                            if total > user.balance:
                                print("Insufficient balance!")
                            else:
                                import random
                                future_price = price * random.uniform(0.8, 1.5)
                                predicted_value = future_price * qty

                                user.balance -= total
                                cursor.execute("UPDATE users SET balance=%s WHERE id=%s", (user.balance, user.id))

                                cursor.execute(
                                    "INSERT INTO investments (user_id,type,amount,returns) VALUES (%s,%s,%s,%s)",
                                    (user.id, name, total, predicted_value-total)
                                )

                                conn.commit()
                                print(f"Bought {name}!\nPredicted future value: ₹{predicted_value}")

                    elif i_choice == 3:
                        cursor.execute("SELECT type,amount,returns,timestamp FROM investments WHERE user_id=%s", (user.id,))
                        data = cursor.fetchall()

                        for d in data:
                            print(f"[{d[3]}] {d[0]} | ₹{d[1]} | Profit: ₹{d[2]}")

                    conn.close()

                except Exception as e:
                    print("Error:", e)



            else:
                print("Invalid Choice")

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