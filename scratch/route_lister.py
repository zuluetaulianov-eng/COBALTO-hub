import os
import sys

# We can parse the file statically to find all routes decoration to avoid importing dependencies
filepath = "app.py"
if not os.path.exists(filepath):
    print("app.py not found")
    sys.exit(1)

print("=== LISTING ALL ROUTES IN app.py ===")
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "@app." in line or "@router." in line:
        # Print decorator and the next 1-2 lines
        print(f"Line {i + 1}: {line.strip()}")
        # print next line
        if i + 1 < len(lines):
            print(f"         {lines[i + 1].strip()}")
