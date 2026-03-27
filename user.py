accounts = []
idCount = 0

def loginPage():
    print("1 for Login\n2 for Sign in")
    c = int(input("Enter choice"))
    if c == 1:
        login()
    elif c == 2:
        createAccount()

def login():
    name = input("Enter Username")
    passw = input("Enter Password")
    
class User:
    name = ""
    id = 0
    balance = 0
    password = "12345678"

    def __init__(self,name,password):
        self.name = name
        self.id = idCount
        idCount += 1
        self.balance = 0
        self.password = password
    
    def display(self):
        print("Name: ", self.name)
        print("ID: ", self.id)
        print("Balance: ", self.balance)
        print("Password: ", self.password)

def createAccount():
    n = input("Enter Name: ")
    p = input("Enter Password: ")
    accounts.append(User(n,p))
    print("\n\n\n")

loginPage()

'''while True:
    choice = int(input("Enter choice: "))
    if choice == 1:
        createAccount()'''
    


