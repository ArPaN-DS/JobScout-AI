#!/usr/bin/env python3
"""
Key Generator for JobScout-AI
Generates secure cryptographic keys (Django secret key and Fernet encryption key)
and safely writes them to the .env file.
"""

import os
import sys
import secrets
import shutil

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Error: The 'cryptography' library is not installed.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)

def generate_django_secret_key():
    # Generate a secure 50-character Django secret key
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(chars) for _ in range(50))

def generate_fernet_key():
    # Generate a standard Fernet key
    return Fernet.generate_key().decode('utf-8')

def main():
    env_file = ".env"
    example_file = ".env.example"

    # Generate keys
    django_key = generate_django_secret_key()
    fernet_key = generate_fernet_key()

    print("--- JobScout-AI Key Generator ---")
    
    if not os.path.exists(env_file):
        if not os.path.exists(example_file):
            print(f"Error: {example_file} not found in the current directory.")
            sys.exit(1)
        
        # Copy .env.example to .env
        shutil.copy(example_file, env_file)
        print(f"Created a new '{env_file}' from '{example_file}'.")

        # Read the newly created .env and replace placeholders
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()

        content = content.replace("your-django-secret-key-here", django_key)
        content = content.replace("your-fernet-encryption-key-here", fernet_key)

        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print("Successfully generated and injected secure keys into your new '.env' file!")
        print(f"  - DJANGO_SECRET_KEY configured.")
        print(f"  - FIELD_ENCRYPTION_KEY configured.")
    else:
        print(f"Found an existing '{env_file}' file.")
        
        # Read the existing .env to check for placeholders
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()

        updated = False
        if "your-django-secret-key-here" in content:
            content = content.replace("your-django-secret-key-here", django_key)
            print("Updated placeholder 'your-django-secret-key-here' in '.env' with a secure key.")
            updated = True
        
        if "your-fernet-encryption-key-here" in content:
            content = content.replace("your-fernet-encryption-key-here", fernet_key)
            print("Updated placeholder 'your-fernet-encryption-key-here' in '.env' with a secure Fernet key.")
            updated = True

        if updated:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print("Successfully updated placeholders in '.env'!")
        else:
            print("\nKeys are already configured in '.env'. To rotate or view secure keys, copy these:")
            print(f"Suggested DJANGO_SECRET_KEY:  {django_key}")
            print(f"Suggested FIELD_ENCRYPTION_KEY: {fernet_key}")
            print("\nNote: Existing active keys in '.env' were NOT overwritten to prevent data decryption issues.")

if __name__ == "__main__":
    main()
