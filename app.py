import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

def db_init():
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            balance REAL DEFAULT 0,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

class User:
    def __init__(self, name, password, user_id=None, balance=0):
        self.name = name
        self.id = user_id
        self.balance = balance
        self.password = password
    
    def display(self):
        print("Name: ", self.name)
        print("ID: ", self.id)
        print("Balance: ", self.balance)
        print("Password: ", self.password)

def login():
    name = input("Enter Username: ")
    passw = input("Enter Password: ")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name=%s AND password=%s", (name, passw))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        user = User(user_data[1], user_data[3], user_data[0], user_data[2])
        print("\nLogin Successful!")
        user.display()
    else:
        print("\nInvalid Credentials!")

def createAccount():
    n = input("Enter Name: ")
    p = input("Enter Password: ")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, password) VALUES (%s, %s)", (n, p))
    conn.commit()
    conn.close()
    
    print("\nAccount created successfully!")
    print("\n\n\n")

def loginPage():
    db_init()
    print("1 for Login\n2 for Sign Up")
    try:
        c = int(input("Enter choice: "))
        if c == 1:
            login()
        elif c == 2:
            createAccount()
        else:
            print("Invalid Choice")
    except ValueError:
        print("Please enter a valid number.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    loginPage()
