import sys

# List of all required modules and libraries to check
modules_to_check = [
    "sys",
    "os",
    "re",
    "base64",
    "binascii",
    "dis",
    "hashlib",
    "secrets",
    "string",
    "marshal",
    "types",
    "datetime",
    "pathlib",
    "PySide6"
]

print("===========================================")
print(" Checking modules and libraries...")
print("===========================================\n")

missing_modules = []

for module_name in modules_to_check:
    try:
        __import__(module_name)
        print(f"[OK] Module '{module_name}' is available.")
    except ImportError:
        print(f"[ERROR] Module '{module_name}' not found!")
        missing_modules.append(module_name)

print("\n===================================================")
if missing_modules:
    print(f"Missing modules: {', '.join(missing_modules)}")
    if "PySide6" in missing_modules:
        print("\nTo install PySide6, run the following command in your terminal:")
        print("   pip install PySide6")
        print("(On macOS, try: python3 -m pip install PySide6)")
else:
    print("All required modules and libraries are installed!")
print("===================================================")

# Keep the terminal window open
input("\nPress Enter to exit...")