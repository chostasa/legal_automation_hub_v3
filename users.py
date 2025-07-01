# users.py

import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

USERS = {
    "chostasa@sgghlaw.com": hash_password("S!282600881348uh!"),
    "kasia": hash_password("Leadership22"),
    "sydney": hash_password("AdminView3"),
    "jordan": hash_password("CaseOps!4"),
}
