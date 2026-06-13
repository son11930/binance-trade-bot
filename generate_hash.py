import getpass
try:
    import bcrypt
except ImportError:
    print("Please install bcrypt first: pip install bcrypt")
    exit(1)

print("========================================")
print("   Bcrypt Password Hash Generator")
print("========================================")
password = getpass.getpass("Enter your desired dashboard password: ")
confirm = getpass.getpass("Confirm password: ")

if password != confirm:
    print("Passwords do not match!")
    exit(1)

# bcrypt requires bytes
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

print("\nSuccess! Replace the DASHBOARD_PASS value in your .env file with the following hash:\n")
print(f"DASHBOARD_PASS=\"{hashed.decode('utf-8')}\"")
print("\n========================================")
