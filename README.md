# CryptoLab Pro

**Beta 4 — Cryptography & Security Toolkit**

CryptoLab Pro is a desktop application written in Python that combines cryptographic tools, encryption algorithms, password hashing, key generation and Python bytecode analysis in one interface.

---

## Features

### Encryption & Decryption

- **AES-256-GCM** — authenticated symmetric encryption.
- **Fernet** — symmetric encryption with integrity verification.
- **Caesar Cipher** — classical substitution cipher.
- **Vigenère Cipher** — polyalphabetic substitution cipher.
- **Atbash** — classical reversed-alphabet cipher.
- **ROT13** — rotational substitution cipher.
- **XOR** — bitwise XOR encryption.

### Enigma Simulator

Educational simulator of the historical Enigma I machine.

- Rotors I–V.
- Configurable rotor positions.
- Ring settings.
- Reflectors B and C.
- Plugboard configuration.

### Hashing

Supported algorithms:

- SHA-224
- SHA-256
- SHA-384
- SHA-512
- SHA3-256
- SHA3-512
- BLAKE2b
- BLAKE2s

### Password Hashing

- Argon2id
- Scrypt
- PBKDF2-SHA256
- PBKDF2-SHA512

### Key Generator

- Cryptographically secure random key generation.
- AES-128, AES-192 and AES-256.
- HEX and Base64 formats.

### Python Bytecode Analyzer

Tools for examining compiled Python `.pyc` files.

- Bytecode inspection.
- Compiled file structure analysis.
- Bytecode research.

---

## Technologies

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| PySide6 | Graphical user interface |
| Cryptography | Cryptographic operations |
| Argon2-cffi | Argon2id password hashing |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/VadymTS1-phab/ProCrypto.git
cd ProCrypto
```

### 2. Install dependencies

```bash
python3 -m pip install PySide6 cryptography argon2-cffi
```

### 3. Run the application

```bash
python3 main.py
```

Replace `main.py` with the actual entry-point filename if necessary.

---

## Security Notice

CryptoLab Pro includes both modern cryptographic algorithms and classical educational ciphers.

- AES-GCM and Fernet are intended for data protection.
- Argon2id, Scrypt and PBKDF2 are designed for password hashing or key derivation.
- Classical ciphers such as Caesar, ROT13, Atbash, Vigenère and Enigma are not suitable for protecting sensitive information.
- Hashing is a one-way operation and is not encryption.

The application should not be considered independently audited security software.

---

## Development Status

**Current Version: Beta 3**

CryptoLab Pro is actively developed. Features, interface elements and internal implementation may change in future releases.

---

## Author

**VadymTS1**

- GitHub: [@VadymTS1-phab](https://github.com/VadymTS1-phab)
- Repository: [ProCrypto](https://github.com/VadymTS1-phab/ProCrypto)

---

<p align="center">
  <strong>CryptoLab Pro</strong><br>
  Cryptography in one place.
</p>
