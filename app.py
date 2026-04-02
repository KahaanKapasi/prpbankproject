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
            )
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
        print("5. Logout")

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
                print("Logging out...")
                break

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