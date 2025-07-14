# users.py

import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

USERS = {
    "chostasa@sgghlaw.com": hash_password("S!282600881348uh!"),
    "toliver@sgghlaw.com": hash_password("G)177471332680ux"),
    "qyu@sgghlaw.com": hash_password("5211384XMqo!"),
    "kasia": hash_password("Leadership22"),
}
