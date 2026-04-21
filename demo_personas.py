PERSONAS = [
    {
        "username": "admin",
        "password": "admin",
        "full_name": "PRP Bank Admin",
        "email": "admin@prpbank.in",
        "phone": "+91 90000 00001",
        "role": "ADMIN",
        "hint": "Bank operator (admin panel)",
        "wallet": 0,
        "savings": 0,
    },
    {
        "username": "alice",
        "password": "alice",
        "full_name": "Alice Sharma",
        "email": "alice.sharma@example.in",
        "phone": "+91 90000 12345",
        "role": "USER",
        "hint": "Everyday customer",
        "wallet": 85000,
        "savings": 150000,
    },
    {
        "username": "bob",
        "password": "bob",
        "full_name": "Bob Mehta",
        "email": "bob.mehta@example.in",
        "phone": "+91 90000 22334",
        "role": "USER",
        "hint": "Loan-heavy, with overdue bill",
        "wallet": 12000,
        "savings": 5000,
    },
    {
        "username": "carol",
        "password": "carol",
        "full_name": "Carol D'Souza",
        "email": "carol.dsouza@example.in",
        "phone": "+91 90000 33445",
        "role": "USER",
        "hint": "Investor, large portfolio",
        "wallet": 250000,
        "savings": 500000,
    },
    {
        "username": "dev",
        "password": "dev",
        "full_name": "Dev Iyer",
        "email": "dev.iyer@example.in",
        "phone": "+91 90000 44556",
        "role": "USER",
        "hint": "New user (empty states)",
        "wallet": 500,
        "savings": 0,
    },
    {
        "username": "eve",
        "password": "eve",
        "full_name": "Eve Khan",
        "email": "eve.khan@example.in",
        "phone": "+91 90000 55667",
        "role": "USER",
        "hint": "Counterparty (receives cheques)",
        "wallet": 50000,
        "savings": 20000,
    },
]


def public_personas():
    """Personas exposed to the login screen (no passwords leaked at render time
    — passwords are looked up server-side from this list)."""
    return [
        {"username": p["username"], "hint": p["hint"], "role": p["role"]}
        for p in PERSONAS
    ]


def find_persona(username):
    for p in PERSONAS:
        if p["username"] == username:
            return p
    return None
