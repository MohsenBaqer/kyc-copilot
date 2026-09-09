import os
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("ANTHROPIC_API_KEY")

if key:
    print(f"Key loaded successfully. Starts with: {key[:12]}...")
else:
    print("Key NOT found. Check your .env file.")