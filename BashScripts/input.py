# example.py
import sys

if len(sys.argv) > 1:
    text = sys.argv[1]
    print(f"You entered: {text}")
else:
    print("No text provided")
