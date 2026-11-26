import sys
import json
import os

json_file_name = "modules.json"

# Automatically create modules.json if it doesn't exist
if not os.path.exists(json_file_name):
    default_data = {
        "modules": [
            "sys", "os", "re", "base64", "binascii", "dis", 
            "hashlib", "secrets", "string", "marshal", "types", 
            "datetime", "pathlib", "PySide6"
        ]
    }
    with open(json_file_name, "w", encoding="utf-8") as f:
        json.dump(default_data, f, indent=4)

print("========================================")
print(" Checking modules from JSON...")
print("========================================\n")

# Load modules list from JSON file
try:
    with open(json_file_name, "r", encoding="utf-8") as f:
        data = json.load(f)
        modules_to_check = data.get("modules", [])
except Exception as e:
    print(f"[ERROR] Could not read '{json_file_name}': {e}")
    modules_to_check = []

missing_modules = []

for module_name in modules_to_check:
    try:
        __import__(module_name)
        print(f"[OK] Module '{module_name}' is available.")
    except ImportError:
        print(f"[ERROR] Module '{module_name}' not found!")
        missing_modules.append(module_name)

print("\n========================================")
if missing_modules:
    print(f"Missing modules: {', '.join(missing_modules)}")
    if "PySide6" in missing_modules:
        print("\nTo install PySide6, run the following command in your terminal:")
        print("   pip install PySide6")
        print("(On macOS, try: python3 -m pip install PySide6)")
else:
    print("All required modules and libraries are installed!")
print("========================================")

# Keep the terminal window open
input("\nPress Enter to exit...")