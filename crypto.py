import sys
import os
import base64
import dis
import hashlib
import secrets
import string
import marshal
import types
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QComboBox, QSpinBox, QCheckBox, QMessageBox, QGridLayout, QFileDialog
)

APP_VERSION = "Beta.3"
AUTHOR = "Vadym Tsykvas"
APP_STYLE = """
QWidget { background:#0b1020; color:#e8eefc; font-family:"SF Pro Display","Segoe UI",sans-serif; font-size:14px; }
QFrame#Sidebar { background:#0e1629; border-right:1px solid #202c45; }
QFrame#Card { background:#121d33; border:1px solid #263653; border-radius:16px; }
QLabel#Brand { color:#f4f7ff; font-size:20px; font-weight:800; }
QLabel#Eyebrow { color:#54d6c7; font-size:10px; font-weight:800; letter-spacing:2px; }
QLabel#PageTitle { color:#f5f7ff; font-size:27px; font-weight:800; }
QLabel#Muted { color:#91a0bb; }
QLabel#Metric { color:#fff; font-size:24px; font-weight:800; }
QPushButton { background:#192640; color:#cbd7ed; border:1px solid #2b3b5a; border-radius:10px; padding:10px 14px; font-weight:650; }
QPushButton:hover { background:#223454; border-color:#3c6483; }
QPushButton:checked,QPushButton#Primary { background:#20b9aa; color:#06151b; border:1px solid #20b9aa; }
QPushButton#Nav { text-align:left; padding:12px; background:transparent; border:1px solid transparent; color:#9eacc5; }
QPushButton#Nav:checked { background:#172f40; color:#65e2d4; border:1px solid #245c62; }
QLineEdit,QTextEdit,QComboBox,QSpinBox { background:#0c1528; color:#e8eefc; border:1px solid #2b3c5b; border-radius:9px; padding:9px; }
QCheckBox { color:#aab8d0; spacing:8px; }
"""

def card():
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 18)
    layout.setSpacing(10)
    return frame, layout

def label(text, name=None):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(True)
    return w

def field(text):
    return label(text.upper(), "Eyebrow")

def caesar(text, shift):
    out = []
    for ch in text:
        base = ord('A') if ch.isupper() else ord('a')
        if ch.isalpha() and ch.isascii():
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return ''.join(out)

def vigenere(text, key, decrypt=False):
    key = ''.join(c.lower() for c in key if c.isalpha() and c.isascii())
    if not key:
        raise ValueError("Для Vigenère потрібен ключ з латинських літер.")
    result, j = [], 0
    for ch in text:
        if ch.isascii() and ch.isalpha():
            shift = ord(key[j % len(key)]) - 97
            if decrypt:
                shift = -shift
            base = 65 if ch.isupper() else 97
            result.append(chr((ord(ch) - base + shift) % 26 + base))
            j += 1
        else:
            result.append(ch)
    return ''.join(result)

def xor_bytes(data, key):
    if not key:
        raise ValueError("Ключ не може бути порожнім.")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# Educational Enigma I simulator (In testing).
ENIGMA_ROTORS = {
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}
ENIGMA_REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}

#Enigma process
def enigma_transform(text, rotor_names="I II III", positions="AAA", rings="AAA", reflector="B", plugboard=""):
    """Encrypt/decrypt with a simplified three-rotor Enigma I; letters only step rotors."""
    import re
    names = rotor_names.upper().split()
    if len(names) != 3 or any(n not in ENIGMA_ROTORS for n in names) or len(set(names)) != 3:
        raise ValueError("Оберіть три різні ротори з I, II, III, IV, V.")
    positions, rings = positions.upper(), rings.upper()
    if len(positions) != 3 or len(rings) != 3 or not positions.isalpha() or not rings.isalpha() or not positions.isascii() or not rings.isascii():
        raise ValueError("Початкові позиції та кільця мають бути трьома літерами A–Z, наприклад AAA.")
    if reflector.upper() not in ENIGMA_REFLECTORS:
        raise ValueError("Рефлектор має бути B або C.")
    plug = {}
    pairs = re.findall(r"[A-Za-z]{2}", plugboard.upper())
    compact = re.sub(r"[\s,;:-]", "", plugboard.upper())
    if len(compact) != 2 * len(pairs):
        raise ValueError("Пари штекерної панелі введіть як AB CD EF.")
    used = set()
    for pair in pairs:
        a, b = pair
        if a == b or a in used or b in used:
            raise ValueError("Літера може входити лише в одну пару штекерної панелі.")
        used.update((a, b)); plug[a] = b; plug[b] = a

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    rotors = [ENIGMA_ROTORS[n][0] for n in names]  # left, middle, right
    notches = [ENIGMA_ROTORS[n][1] for n in names]
    pos = [ord(c) - 65 for c in positions]
    ring = [ord(c) - 65 for c in rings]
    reflector_wiring = ENIGMA_REFLECTORS[reflector.upper()]

    def plug_swap(ch): return plug.get(ch, ch)
    def through_rotor(x, idx, reverse=False):
        offset = (pos[idx] - ring[idx]) % 26
        wiring = rotors[idx]
        if not reverse:
            return (ord(wiring[(x + offset) % 26]) - 65 - offset) % 26
        wired = (x + offset) % 26
        return (wiring.index(chr(wired + 65)) - offset) % 26

    out = []
    for ch in text:
        if not (ch.isascii() and ch.isalpha()):
            out.append(ch); continue
        # Enigma's pawl mechanism: middle notch causes double-step.
        middle_at_notch = alphabet[pos[1]] == notches[1]
        right_at_notch = alphabet[pos[2]] == notches[2]
        if middle_at_notch: pos[0] = (pos[0] + 1) % 26
        if middle_at_notch or right_at_notch: pos[1] = (pos[1] + 1) % 26
        pos[2] = (pos[2] + 1) % 26

        x = ord(plug_swap(ch.upper())) - 65
        for idx in (2, 1, 0): x = through_rotor(x, idx, False)
        x = ord(reflector_wiring[x]) - 65
        for idx in (0, 1, 2): x = through_rotor(x, idx, True)
        result = plug_swap(chr(x + 65))
        out.append(result if ch.isupper() else result.lower())
    return "".join(out)

#Language types
TRANSLATIONS = {
    "en": {},
    "uk": {
        "◈  CRYPTOLAB": "◈  CRYPTOLAB",
        "SECURITY TOOLKIT / BETA.3": "НАБІР ІНСТРУМЕНТІВ / BETA.3",
        "LANGUAGE": "МОВА",
        "LOCAL MODE • OFFLINE": "ЛОКАЛЬНИЙ РЕЖИМ • ОФЛАЙН",
        "CRYPTOGRAPHY / LEARNING ENVIRONMENT": "КРИПТОГРАФІЯ / НАВЧАЛЬНЕ СЕРЕДОВИЩЕ",
        "●  SYSTEM READY": "●  СИСТЕМА ГОТОВА",
        "⌂   Overview": "⌂   Огляд",
        "▣   Encryption": "▣   Шифрування",
        "⌗   Hash laboratory": "⌗   Лабораторія хешів",
        "◎   Password lab": "◎   Лабораторія паролів",
        "⚿   Key generator": "⚿   Генератор ключів",
        "⌘   Code laboratory": "⌘   Лабораторія коду",
        "CONTROL CENTER / BETA.3": "ЦЕНТР КЕРУВАННЯ / BETA.3",
        "Welcome to CryptoLab.": "Ласкаво просимо до CryptoLab.",
        "A local workspace for cryptography experiments and code inspection.": "Локальне середовище для експериментів із криптографією та аналізу коду.",
        "05": "05", "LAB MODULES": "МОДУЛІ ЛАБОРАТОРІЇ",
        "08+": "08+", "HASH OPTIONS": "АЛГОРИТМИ ХЕШУВАННЯ",
        "BETA.3": "BETA.3", "RELEASE": "ВЕРСІЯ",
        "WHAT'S NEW IN BETA.3": "ЩО НОВОГО У BETA.3",
        "More classical ciphers, modern authenticated encryption (optional dependency), additional hash functions and password KDFs, key formats, plus Python bytecode inspection.": "Більше класичних шифрів, сучасне автентифіковане шифрування (потрібна додаткова бібліотека), нові хеш-функції та алгоритми отримання ключів із паролів, формати ключів і аналіз байткоду Python.",
        "AUTHOR": "АВТОР",
        "Vadym Tsykvas  •  © 2026. All rights reserved.": "Vadym Tsykvas  •  © 2026. Усі права захищено.",
        "SECURITY NOTE": "ПРИМІТКА З БЕЗПЕКИ",
        "Caesar, Vigenère, Atbash, ROT13 and repeating-key XOR are educational examples, not secure protection. Use AES-GCM or Fernet for real data, and keep keys secret.": "Цезар, Віженер, Atbash, ROT13 та XOR із повторюваним ключем — навчальні приклади, а не надійний захист. Для реальних даних використовуйте AES-GCM або Fernet і зберігайте ключі в таємниці.",
        "CIPHERS / 01": "ШИФРИ / 01",
        "Encryption laboratory": "Лабораторія шифрування",
        "Choose a method. Modern encryption uses the optional cryptography package.": "Оберіть метод. Для сучасного шифрування потрібен додатковий пакет cryptography.",
        "ALGORITHM": "АЛГОРИТМ", "INPUT": "ВХІДНІ ДАНІ", "KEY": "КЛЮЧ", "OUTPUT": "РЕЗУЛЬТАТ",
        "Enter text, or Base64 token when decrypting…": "Введіть текст або токен Base64 для розшифрування…",
        "Key / password / shift (as required)": "Ключ / пароль / зсув (залежно від алгоритму)",
        "Encrypt": "Зашифрувати", "Decrypt": "Розшифрувати",
        "AES-GCM and Fernet output is a Base64 token containing the nonce/metadata and ciphertext. The key is shown only when generated for encryption; save it safely.": "Результат AES-GCM і Fernet — токен Base64 із nonce/метаданими та шифротекстом. Під час шифрування згенерований ключ показується в полі ключа — збережіть його в безпечному місці.",
        "HASH FUNCTIONS / 02": "ХЕШ-ФУНКЦІЇ / 02",
        "Hash laboratory": "Лабораторія хешів",
        "Calculate a digest and compare two hash strings.": "Обчислюйте хеш і порівнюйте два хеш-рядки.",
        "HASH ALGORITHM": "АЛГОРИТМ ХЕШУВАННЯ", "Text to hash…": "Текст для хешування…",
        "Calculate digest": "Обчислити хеш", "DIGEST": "ХЕШ",
        "Copy digest": "Копіювати хеш", "DIGEST COMPARISON": "ПОРІВНЯННЯ ХЕШІВ",
        "First digest": "Перший хеш", "Second digest": "Другий хеш", "Compare": "Порівняти",
        "Comparison result will appear here.": "Тут з’явиться результат порівняння.",
        "MD5 and SHA-1 are included only for compatibility/testing; do not use them for security-sensitive integrity or passwords.": "MD5 і SHA-1 додані лише для сумісності та тестування. Не використовуйте їх для захисту даних або паролів.",
        "PASSWORD SECURITY / 03": "БЕЗПЕКА ПАРОЛІВ / 03",
        "Password laboratory": "Лабораторія паролів",
        "Derive password hashes using salts and configurable key-derivation algorithms.": "Отримуйте хеші паролів із сіллю та різними алгоритмами.",
        "SAMPLE PASSWORD": "ТЕСТОВИЙ ПАРОЛЬ",
        "Use a test password, not your real account password": "Введіть тестовий пароль, а не пароль від реального облікового запису",
        "KDF ALGORITHM": "АЛГОРИТМ KDF", "Show sample password": "Показати тестовий пароль",
        "Derive password hash": "Обчислити хеш пароля", "SALT (HEX)": "СІЛЬ (HEX)",
        "DERIVED HASH (HEX)": "ОТРИМАНИЙ ХЕШ (HEX)",
        "Argon2id requires: python3 -m pip install argon2-cffi. Keep the salt with the hash; it is not a secret.": "Для Argon2id встановіть: python3 -m pip install argon2-cffi. Зберігайте сіль разом із хешем; сіль не є секретом.",
        "RANDOMNESS / 04": "ВИПАДКОВІСТЬ / 04",
        "Key generator": "Генератор ключів",
        "Generate random material using Python's cryptographically secure random source.": "Генеруйте випадкові дані за допомогою криптографічно стійкого генератора Python.",
        "KEY TYPE": "ТИП КЛЮЧА", "TEXT KEY LENGTH": "ДОВЖИНА ТЕКСТОВОГО КЛЮЧА",
        "Include symbols in random text": "Додавати символи до випадкового тексту",
        "OUTPUT FORMAT": "ФОРМАТ РЕЗУЛЬТАТУ", "Generate key": "Згенерувати ключ",
        "GENERATED KEY": "ЗГЕНЕРОВАНИЙ КЛЮЧ", "Copy key": "Копіювати ключ",
        "CODE LABORATORY / 05": "ЛАБОРАТОРІЯ КОДУ / 05",
        "Python bytecode inspector": "Аналізатор байткоду Python",
        "Inspect a Python .pyc file and display its bytecode instructions. This is a lightweight disassembler, not a full source-code recovery tool.": "Аналізуйте файл Python .pyc і переглядайте інструкції байткоду. Це простий дизасемблер, а не повноцінний засіб відновлення початкового коду.",
        "Open .pyc file": "Відкрити файл .pyc",
        "Bytecode output will appear here…": "Тут з’явиться результат аналізу байткоду…",
        "LIMITATIONS": "ОБМЕЖЕННЯ",
        "Python bytecode is version-specific. Use the same Python major/minor version that created the .pyc file. The tool shows disassembled instructions and metadata; it does not execute the file or guarantee reconstruction of original source.": "Байткод Python залежить від версії. Використовуйте ту саму основну та додаткову версію Python, якою створено .pyc. Інструмент показує інструкції та метадані, не запускає файл і не гарантує відновлення оригінального коду.",
        "Random text": "Випадковий текст", "AES-128 (16 bytes)": "AES-128 (16 байтів)",
        "AES-192 (24 bytes)": "AES-192 (24 байти)", "AES-256 (32 bytes)": "AES-256 (32 байти)",
        "32 random bytes": "32 випадкові байти", "64 random bytes": "64 випадкові байти",
        "Hex": "Hex", "Base64": "Base64", "Text (random text only)": "Текст (лише випадковий текст)",
        "Caesar": "Цезар", "ROT13": "ROT13", "Atbash": "Atbash", "Vigenère": "Віженер",
        "Caesar shift (0–25)": "Зсув Цезаря (0–25)",
        "Rotors left to right (I–V)": "Ротори зліва направо (I–V)",
        "Start positions (3 letters)": "Початкові позиції (3 літери)",
        "Ring settings (3 letters)": "Налаштування кілець (3 літери)",
        "Reflector": "Рефлектор", "Plugboard pairs": "Пари штекерної панелі",
        "CAESAR SHIFT (0–25)": "ЗСУВ ЦЕЗАРЯ (0–25)",
        "ROTORS LEFT TO RIGHT (I–V)": "РОТОРИ ЗЛІВА НАПРАВО (I–V)",
        "START POSITIONS (3 LETTERS)": "ПОЧАТКОВІ ПОЗИЦІЇ (3 ЛІТЕРИ)",
        "RING SETTINGS (3 LETTERS)": "НАЛАШТУВАННЯ КІЛЕЦЬ (3 ЛІТЕРИ)",
        "REFLECTOR": "РЕФЛЕКТОР", "PLUGBOARD PAIRS": "ПАРИ ШТЕКЕРНОЇ ПАНЕЛІ",
        "Enigma I (educational)": "Енігма I (навчальна)",
        "Repeating-key XOR (demo)": "XOR із повторюваним ключем (демо)",
        "AES-256-GCM": "AES-256-GCM", "Fernet": "Fernet",
        "SHA-224": "SHA-224", "SHA-256": "SHA-256", "SHA-384": "SHA-384",
        "SHA-512": "SHA-512", "SHA3-256": "SHA3-256", "SHA3-512": "SHA3-512",
        "BLAKE2b": "BLAKE2b", "BLAKE2s": "BLAKE2s",
        "SHA-1 (legacy only)": "SHA-1 (застарілий)", "MD5 (legacy only)": "MD5 (застарілий)",
        "PBKDF2-HMAC-SHA256": "PBKDF2-HMAC-SHA256",
        "PBKDF2-HMAC-SHA512": "PBKDF2-HMAC-SHA512", "scrypt": "scrypt",
        "Argon2id (optional package)": "Argon2id (додатковий пакет)",
        "Enter a sample password first.": "Спочатку введіть тестовий пароль.",
        "Missing input": "Немає вхідних даних", "Operation failed": "Помилка операції",
        "Hash error": "Помилка хешування", "KDF error": "Помилка KDF",
        "Missing package": "Відсутній пакет",
        "Install Argon2 support with: python3 -m pip install argon2-cffi": "Встановіть підтримку Argon2 командою: python3 -m pip install argon2-cffi",
        "Select Python bytecode": "Виберіть байткод Python",
        "Could not inspect bytecode": "Не вдалося проаналізувати байткод",
        "The file does not contain a recognized Python code object.": "Файл не містить розпізнаного об’єкта коду Python.",
        "File is too short to be a standard modern .pyc file.": "Файл надто короткий для стандартного сучасного формату .pyc.",
        "Enter both digests.": "Введіть обидва хеші.",
        "✓ MATCH — digests are identical.": "✓ ЗБІГ — хеші однакові.",
        "✕ NO MATCH — digests differ.": "✕ НЕ ЗБІГАЮТЬСЯ — хеші різні.",
    }
}

#owerview
class CryptoLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"CryptoLab Pro {APP_VERSION}")
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.nav_buttons = []

        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(225)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(17, 24, 17, 18)
        side.setSpacing(9)
        side.addWidget(label("◈  CRYPTOLAB", "Brand"))
        side.addWidget(label("SECURITY TOOLKIT / BETA.3", "Eyebrow"))
        side.addSpacing(12)
        side.addWidget(label("LANGUAGE", "Eyebrow"))
        self.language_selector = QComboBox()
        self.language_selector.setObjectName("LanguageSelector")
        self.language_selector.addItems(["English", "Українська"])
        side.addWidget(self.language_selector)
        side.addSpacing(12)

        self.stack = QStackedWidget()
        pages = [
            ("⌂   Overview", self.dashboard_page),
            ("▣   Encryption", self.encryption_page),
            ("⌗   Hash laboratory", self.hash_page),
            ("◎   Password lab", self.password_page),
            ("⚿   Key generator", self.key_page),
            ("⌘   Code laboratory", self.code_page),
        ]
        for i, (name, builder) in enumerate(pages):
            btn = QPushButton(name)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, index=i: self.switch_page(index))
            side.addWidget(btn)
            self.nav_buttons.append(btn)
            self.stack.addWidget(builder())
        side.addStretch()
        side.addWidget(label("LOCAL MODE • OFFLINE", "Eyebrow"))
        side.addWidget(label(f"CryptoLab Pro {APP_VERSION}", "Muted"))

        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(28, 23, 28, 22)
        ml.addWidget(label("CRYPTOGRAPHY / LEARNING ENVIRONMENT", "Eyebrow"))
        status = label("●  SYSTEM READY")
        status.setStyleSheet("color:#5de0bd;font-size:11px;font-weight:800;")
        ml.addWidget(status)
        ml.addWidget(self.stack, 1)
        outer.addWidget(sidebar)
        outer.addWidget(main, 1)
        self._capture_original_ui()
        self.language_selector.currentIndexChanged.connect(self.apply_language)
        self.switch_page(0)

    def _capture_original_ui(self):
        self._original_text = {}
        self._original_placeholders = {}
        self._original_combo_items = {}
        for widget in self.findChildren(QWidget):
            if widget is self.language_selector:
                continue
            if hasattr(widget, "text") and callable(widget.text):
                try:
                    self._original_text[widget] = widget.text()
                except TypeError:
                    pass
            if hasattr(widget, "placeholderText"):
                try:
                    self._original_placeholders[widget] = widget.placeholderText()
                except TypeError:
                    pass
            if isinstance(widget, QComboBox):
                self._original_combo_items[widget] = [widget.itemText(i) for i in range(widget.count())]

    def apply_language(self, index):
        lang = "uk" if index == 1 else "en"
        catalog = TRANSLATIONS[lang]
        for widget, original in self._original_text.items():
            translated = catalog.get(original, original)
            if isinstance(widget, QLabel):
                widget.setText(translated)
            elif isinstance(widget, QPushButton):
                widget.setText(translated)
            elif isinstance(widget, QCheckBox):
                widget.setText(translated)
        for widget, original in self._original_placeholders.items():
            widget.setPlaceholderText(catalog.get(original, original))
        for widget, items in self._original_combo_items.items():
            if widget is self.language_selector:
                continue
            current = widget.currentIndex()
            widget.blockSignals(True)
            for i, original in enumerate(items):
                widget.setItemText(i, catalog.get(original, original))
            widget.setCurrentIndex(current)
            widget.blockSignals(False)
        if hasattr(self, "cipher"):
            self.update_cipher_controls(self.cipher.currentText())

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def shell(self, eyebrow, title, desc):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)
        layout.addWidget(label(eyebrow, "Eyebrow"))
        layout.addWidget(label(title, "PageTitle"))
        layout.addWidget(label(desc, "Muted"))
        return page, layout

    def dashboard_page(self):
        page, layout = self.shell("CONTROL CENTER / BETA.3", "Welcome to CryptoLab.", "A local workspace for cryptography experiments and code inspection.")
        grid = QGridLayout()
        for i, (num, caption) in enumerate([("05", "LAB MODULES"), ("08+", "HASH OPTIONS"), ("BETA.3", "RELEASE")]):
            box, b = card()
            b.addWidget(label(num, "Metric"))
            b.addWidget(label(caption, "Eyebrow"))
            grid.addWidget(box, 0, i)
        layout.addLayout(grid)
        box, b = card()
        b.addWidget(label("WHAT'S NEW IN BETA.3", "Eyebrow"))
        b.addWidget(label("More classical ciphers, modern authenticated encryption (optional dependency), additional hash functions and password KDFs, key formats, plus Python bytecode inspection.", "Muted"))
        b.addWidget(label("AUTHOR", "Eyebrow"))
        b.addWidget(label(f"{AUTHOR}  •  © 2026. All rights reserved.", "Muted"))
        layout.addWidget(box)
        note, n = card()
        n.addWidget(label("SECURITY NOTE", "Eyebrow"))
        n.addWidget(label("Caesar, Vigenère, Atbash, ROT13 and repeating-key XOR are educational examples, not secure protection. Use AES-GCM or Fernet for real data, and keep keys secret.", "Muted"))
        layout.addWidget(note)
        layout.addStretch()
        return page

    def encryption_page(self):
        page, layout = self.shell("CIPHERS / 01", "Encryption laboratory", "Choose a method. Modern encryption uses the optional cryptography package.")
        box, b = card()
        self.cipher = QComboBox()
        self.cipher.addItems(["Caesar", "ROT13", "Atbash", "Vigenère", "Repeating-key XOR (demo)", "Enigma I (educational)", "AES-256-GCM", "Fernet"])
        b.addWidget(field("Algorithm"))
        b.addWidget(self.cipher)
        self.caesar_shift_label = field("Caesar shift (0–25)")
        b.addWidget(self.caesar_shift_label)
        self.caesar_shift = QSpinBox()
        self.caesar_shift.setRange(0, 25)
        self.caesar_shift.setValue(3)
        b.addWidget(self.caesar_shift)
        self.enigma_panel = QWidget()
        eg = QGridLayout(self.enigma_panel)
        eg.setContentsMargins(0, 4, 0, 4)
        self.enigma_rotors = QLineEdit("I II III")
        self.enigma_positions = QLineEdit("AAA")
        self.enigma_rings = QLineEdit("AAA")
        self.enigma_reflector = QComboBox(); self.enigma_reflector.addItems(["B", "C"])
        self.enigma_plugboard = QLineEdit(); self.enigma_plugboard.setPlaceholderText("AB CD EF (optional)")
        eg.addWidget(field("Rotors left to right (I–V)"), 0, 0); eg.addWidget(self.enigma_rotors, 0, 1)
        eg.addWidget(field("Start positions (3 letters)"), 1, 0); eg.addWidget(self.enigma_positions, 1, 1)
        eg.addWidget(field("Ring settings (3 letters)"), 2, 0); eg.addWidget(self.enigma_rings, 2, 1)
        eg.addWidget(field("Reflector"), 3, 0); eg.addWidget(self.enigma_reflector, 3, 1)
        eg.addWidget(field("Plugboard pairs"), 4, 0); eg.addWidget(self.enigma_plugboard, 4, 1)
        b.addWidget(self.enigma_panel)
        self.cipher.currentTextChanged.connect(self.update_cipher_controls)
        self.update_cipher_controls(self.cipher.currentText())
        self.enc_input = QTextEdit()
        self.enc_input.setPlaceholderText("Enter text, or Base64 token when decrypting…")
        self.enc_input.setFixedHeight(115)
        b.addWidget(field("Input"))
        b.addWidget(self.enc_input)
        self.cipher_key = QLineEdit()
        self.cipher_key.setPlaceholderText("Key / password / shift (as required)")
        b.addWidget(field("Key"))
        row = QHBoxLayout()
        enc = QPushButton("Encrypt")
        enc.setObjectName("Primary")
        dec = QPushButton("Decrypt")
        enc.clicked.connect(lambda: self.run_cipher(True))
        dec.clicked.connect(lambda: self.run_cipher(False))
        row.addWidget(enc)
        row.addWidget(dec)
        row.addStretch()
        b.addLayout(row)
        self.enc_output = QTextEdit()
        self.enc_output.setReadOnly(True)
        self.enc_output.setFixedHeight(130)
        b.addWidget(field("Output"))
        b.addWidget(self.enc_output)
        layout.addWidget(box)
        layout.addWidget(label("AES-GCM and Fernet output is a Base64 token containing the nonce/metadata and ciphertext. The key is shown only when generated for encryption; save it safely. Enigma I is a historical educational simulator, not secure encryption.", "Muted"))
        layout.addStretch()
        return page

    def canonical_text(self, text):
        """Return the English internal identifier even when the UI is in Ukrainian."""
        if self.language_selector.currentIndex() == 1:
            reverse = {translated: original for original, translated in TRANSLATIONS["uk"].items()}
            return reverse.get(text, text)
        return text

    def update_cipher_controls(self, method):
        method = self.canonical_text(method)
        self.caesar_shift_label.setVisible(method == "Caesar")
        self.caesar_shift.setVisible(method == "Caesar")
        self.enigma_panel.setVisible(method == "Enigma I (educational)")
        if hasattr(self, "cipher_key"):
            self.cipher_key.setVisible(method != "Enigma I (educational)")

    def run_cipher(self, encrypt):
        text = self.enc_input.toPlainText()
        key = self.cipher_key.text()
        method = self.canonical_text(self.cipher.currentText())
        try:
            if method == "Caesar":
                shift = self.caesar_shift.value() * (1 if encrypt else -1)
                result = caesar(text, shift)
            elif method == "ROT13":
                result = caesar(text, 13)
            elif method == "Atbash":
                result = ''.join(chr((ord(c)-65 if c.isupper() else ord(c)-97) * -1 % 26 + (65 if c.isupper() else 97)) if c.isascii() and c.isalpha() else c for c in text)
            elif method == "Vigenère":
                result = vigenere(text, key, not encrypt)
            elif method == "Repeating-key XOR (demo)":
                if not key:
                    raise ValueError("Вкажи ключ.")
                if encrypt:
                    raw = xor_bytes(text.encode("utf-8"), key.encode("utf-8"))
                    result = base64.b64encode(raw).decode()
                else:
                    raw = base64.b64decode(text, validate=True)
                    result = xor_bytes(raw, key.encode("utf-8")).decode("utf-8")
            elif method == "Enigma I (educational)":
                result = enigma_transform(
                    text,
                    self.enigma_rotors.text(),
                    self.enigma_positions.text(),
                    self.enigma_rings.text(),
                    self.enigma_reflector.currentText(),
                    self.enigma_plugboard.text(),
                )
            elif method in ("AES-256-GCM", "Fernet"):
                try:
                    if method == "AES-256-GCM":
                        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                        if encrypt:
                            raw_key = secrets.token_bytes(32) if not key else bytes.fromhex(key)
                            if len(raw_key) != 32:
                                raise ValueError("AES-256 потребує ключ рівно 32 байти (64 hex-символи).")
                            nonce = secrets.token_bytes(12)
                            token = nonce + AESGCM(raw_key).encrypt(nonce, text.encode(), None)
                            result = base64.b64encode(token).decode()
                            self.cipher_key.setText(raw_key.hex())
                        else:
                            raw_key = bytes.fromhex(key)
                            token = base64.b64decode(text, validate=True)
                            result = AESGCM(raw_key).decrypt(token[:12], token[12:], None).decode()
                    else:
                        from cryptography.fernet import Fernet
                        if encrypt:
                            fkey = key.encode() if key else Fernet.generate_key()
                            f = Fernet(fkey)
                            result = f.encrypt(text.encode()).decode()
                            self.cipher_key.setText(fkey.decode())
                        else:
                            result = Fernet(key.encode()).decrypt(text.encode()).decode()
                except ImportError:
                    raise RuntimeError("Потрібна бібліотека cryptography. Встанови: python3 -m pip install cryptography")
            self.enc_output.setPlainText(result)
        except Exception as exc:
            QMessageBox.warning(self, "Operation failed", str(exc))

    def hash_page(self):
        page, layout = self.shell("HASH FUNCTIONS / 02", "Hash laboratory", "Calculate a digest and compare two hash strings.")
        box, b = card()
        self.hash_alg = QComboBox()
        self.hash_alg.addItems(["SHA-224", "SHA-256", "SHA-384", "SHA-512", "SHA3-256", "SHA3-512", "BLAKE2b", "BLAKE2s", "SHA-1 (legacy only)", "MD5 (legacy only)"])
        b.addWidget(field("Hash algorithm"))
        b.addWidget(self.hash_alg)
        self.hash_input = QTextEdit()
        self.hash_input.setPlaceholderText("Text to hash…")
        self.hash_input.setFixedHeight(100)
        b.addWidget(field("Input"))
        b.addWidget(self.hash_input)
        run = QPushButton("Calculate digest")
        run.setObjectName("Primary")
        run.clicked.connect(self.make_hash)
        b.addWidget(run, alignment=Qt.AlignLeft)
        self.hash_output = QLineEdit()
        self.hash_output.setReadOnly(True)
        b.addWidget(field("Digest"))
        b.addWidget(self.hash_output)
        copy = QPushButton("Copy digest")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.hash_output.text()))
        b.addWidget(copy, alignment=Qt.AlignLeft)
        layout.addWidget(box)
        cmp, c = card()
        c.addWidget(label("DIGEST COMPARISON", "Eyebrow"))
        self.compare_a = QLineEdit()
        self.compare_a.setPlaceholderText("First digest")
        self.compare_b = QLineEdit()
        self.compare_b.setPlaceholderText("Second digest")
        c.addWidget(self.compare_a)
        c.addWidget(self.compare_b)
        btn = QPushButton("Compare")
        btn.clicked.connect(self.compare_hashes)
        c.addWidget(btn, alignment=Qt.AlignLeft)
        self.compare_result = label("Comparison result will appear here.", "Muted")
        c.addWidget(self.compare_result)
        layout.addWidget(cmp)
        layout.addWidget(label("MD5 and SHA-1 are included only for compatibility/testing; do not use them for security-sensitive integrity or passwords.", "Muted"))
        layout.addStretch()
        return page

    def make_hash(self):
        name = self.canonical_text(self.hash_alg.currentText()).lower().replace("-", "")
        data = self.hash_input.toPlainText().encode()
        try:
            if name == "blake2b":
                digest = hashlib.blake2b(data).hexdigest()
            elif name == "blake2s":
                digest = hashlib.blake2s(data).hexdigest()
            else:
                digest = hashlib.new(name, data).hexdigest()
            self.hash_output.setText(digest)
        except Exception as exc:
            QMessageBox.warning(self, "Hash error", str(exc))

    def compare_hashes(self):
        a, b = self.compare_a.text().strip().lower(), self.compare_b.text().strip().lower()
        if not a or not b:
            self.compare_result.setText("Enter both digests.")
        elif secrets.compare_digest(a, b):
            self.compare_result.setText("✓ MATCH — digests are identical.")
            self.compare_result.setStyleSheet("color:#5de0bd;font-weight:700;")
        else:
            self.compare_result.setText("✕ NO MATCH — digests differ.")
            self.compare_result.setStyleSheet("color:#ff9b9b;font-weight:700;")

    def password_page(self):
        page, layout = self.shell("PASSWORD SECURITY / 03", "Password laboratory", "Derive password hashes using salts and configurable key-derivation algorithms.")
        box, b = card()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Use a test password, not your real account password")
        b.addWidget(field("Sample password"))
        b.addWidget(self.password_input)
        self.kdf = QComboBox()
        self.kdf.addItems(["PBKDF2-HMAC-SHA256", "PBKDF2-HMAC-SHA512", "scrypt", "Argon2id (optional package)"])
        b.addWidget(field("KDF algorithm"))
        b.addWidget(self.kdf)
        self.show_password = QCheckBox("Show sample password")
        self.show_password.toggled.connect(lambda checked: self.password_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password))
        b.addWidget(self.show_password)
        run = QPushButton("Derive password hash")
        run.setObjectName("Primary")
        run.clicked.connect(self.make_password_hash)
        b.addWidget(run, alignment=Qt.AlignLeft)
        self.salt_output = QLineEdit()
        self.salt_output.setReadOnly(True)
        b.addWidget(field("Salt (hex)"))
        b.addWidget(self.salt_output)
        self.password_hash_output = QTextEdit()
        self.password_hash_output.setReadOnly(True)
        self.password_hash_output.setFixedHeight(90)
        b.addWidget(field("Derived hash (hex)"))
        b.addWidget(self.password_hash_output)
        layout.addWidget(box)
        layout.addWidget(label("Argon2id requires: python3 -m pip install argon2-cffi. Keep the salt with the hash; it is not a secret.", "Muted"))
        layout.addStretch()
        return page

    def make_password_hash(self):
        password = self.password_input.text()
        if not password:
            QMessageBox.information(self, "Missing input" if self.language_selector.currentIndex() == 0 else "Немає вхідних даних", "Enter a sample password first." if self.language_selector.currentIndex() == 0 else "Спочатку введіть тестовий пароль.")
            return
        salt = secrets.token_bytes(16)
        name = self.canonical_text(self.kdf.currentText())
        try:
            if name == "PBKDF2-HMAC-SHA256":
                derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000, dklen=32)
            elif name == "PBKDF2-HMAC-SHA512":
                derived = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 600_000, dklen=64)
            elif name == "scrypt":
                derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
            else:
                from argon2.low_level import hash_secret_raw, Type
                derived = hash_secret_raw(password.encode(), salt, time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, type=Type.ID)
            self.salt_output.setText(salt.hex())
            self.password_hash_output.setPlainText(derived.hex())
        except ImportError:
            QMessageBox.warning(self, "Missing package", "Install Argon2 support with: python3 -m pip install argon2-cffi")
        except Exception as exc:
            QMessageBox.warning(self, "KDF error", str(exc))

    def key_page(self):
        page, layout = self.shell("RANDOMNESS / 04", "Key generator", "Generate random material using Python's cryptographically secure random source.")
        box, b = card()
        self.key_type = QComboBox()
        self.key_type.addItems(["Random text", "AES-128 (16 bytes)", "AES-192 (24 bytes)", "AES-256 (32 bytes)", "32 random bytes", "64 random bytes"])
        b.addWidget(field("Key type"))
        b.addWidget(self.key_type)
        self.key_length = QSpinBox()
        self.key_length.setRange(8, 256)
        self.key_length.setValue(32)
        b.addWidget(field("Text key length"))
        b.addWidget(self.key_length)
        self.key_symbols = QCheckBox("Include symbols in random text")
        self.key_symbols.setChecked(True)
        b.addWidget(self.key_symbols)
        self.key_format = QComboBox()
        self.key_format.addItems(["Hex", "Base64", "Text (random text only)"])
        b.addWidget(field("Output format"))
        b.addWidget(self.key_format)
        run = QPushButton("Generate key")
        run.setObjectName("Primary")
        run.clicked.connect(self.make_key)
        b.addWidget(run, alignment=Qt.AlignLeft)
        self.key_output = QTextEdit()
        self.key_output.setReadOnly(True)
        self.key_output.setFixedHeight(110)
        b.addWidget(field("Generated key"))
        b.addWidget(self.key_output)
        copy = QPushButton("Copy key")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.key_output.toPlainText()))
        b.addWidget(copy, alignment=Qt.AlignLeft)
        layout.addWidget(box)
        layout.addStretch()
        return page

    def make_key(self):
        kind = self.canonical_text(self.key_type.currentText())
        fmt = self.canonical_text(self.key_format.currentText())
        if kind == "Random text":
            alphabet = string.ascii_letters + string.digits
            if self.key_symbols.isChecked():
                alphabet += "!@#$%^&*()-_=+[]{}"
            result = ''.join(secrets.choice(alphabet) for _ in range(self.key_length.value()))
            if fmt != "Text (random text only)":
                raw = result.encode()
                result = raw.hex() if fmt == "Hex" else base64.b64encode(raw).decode()
        else:
            size = {"AES-128 (16 bytes)":16, "AES-192 (24 bytes)":24, "AES-256 (32 bytes)":32, "32 random bytes":32, "64 random bytes":64}[kind]
            raw = secrets.token_bytes(size)
            result = raw.hex() if fmt != "Base64" else base64.b64encode(raw).decode()
        self.key_output.setPlainText(result)

    def code_page(self):
        page, layout = self.shell("CODE LABORATORY / 05", "Python bytecode inspector", "Inspect a Python .pyc file and display its bytecode instructions. This is a lightweight disassembler, not a full source-code recovery tool.")
        box, b = card()
        row = QHBoxLayout()
        choose = QPushButton("Open .pyc file")
        choose.setObjectName("Primary")
        choose.clicked.connect(self.open_pyc)
        row.addWidget(choose)
        row.addStretch()
        b.addLayout(row)
        self.code_output = QTextEdit()
        self.code_output.setReadOnly(True)
        self.code_output.setPlaceholderText("Bytecode output will appear here…")
        b.addWidget(self.code_output)
        layout.addWidget(box)
        note, n = card()
        n.addWidget(label("LIMITATIONS", "Eyebrow"))
        n.addWidget(label("Python bytecode is version-specific. Use the same Python major/minor version that created the .pyc file. The tool shows disassembled instructions and metadata; it does not execute the file or guarantee reconstruction of original source.", "Muted"))
        layout.addWidget(note)
        layout.addStretch()
        return page

    def open_pyc(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Python bytecode", "", "Python bytecode (*.pyc);;All files (*)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if len(raw) < 16:
                raise ValueError("File is too short to be a standard modern .pyc file.")
            code_obj = marshal.loads(raw[16:])
            if not isinstance(code_obj, types.CodeType):
                raise ValueError("The file does not contain a recognized Python code object.")
            lines = [f"File: {os.path.basename(path)}", f"Python runtime: {sys.version.split()[0]}", f"Module: {code_obj.co_name}", f"Constants: {code_obj.co_consts!r}", f"Names: {code_obj.co_names!r}", "", "DISASSEMBLY", "-" * 60]
            lines.append(dis.Bytecode(code_obj).dis())
            for const in code_obj.co_consts:
                if isinstance(const, types.CodeType):
                    lines.extend(["", f"NESTED CODE OBJECT: {const.co_name}", "-" * 60, dis.Bytecode(const).dis()])
            self.code_output.setPlainText("\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Could not inspect bytecode", f"{exc}\n\nПереконайся, що .pyc створений сумісною версією Python.")

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = CryptoLab()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
