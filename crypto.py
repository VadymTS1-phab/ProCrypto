import sys
import os
import re
import base64
import binascii
import dis
import hashlib
import secrets
import string
import marshal
import types
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QComboBox, QSpinBox, QCheckBox, QMessageBox, QGridLayout, QFileDialog,
    QScrollArea
)

APP_VERSION = "Beta.4"
AUTHOR = "Vadym Tsykvas"
APP_STYLE = """
QWidget { background:#0b1020; color:#e8eefc; font-family:__FONTS__; font-size:14px; }
QLabel, QCheckBox { background:transparent; }
QFrame#Sidebar { background:#0e1629; border-right:1px solid #202c45; }
QFrame#Card { background:#121d33; border:1px solid #263653; border-radius:16px; }
QFrame#SubCard { background:#0e182c; border:1px solid #2b3c5b; border-radius:12px; }
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
QPushButton:disabled { background:#111a2d; color:#5c6b86; border-color:#1f2b44; }
QPushButton#Primary:disabled { background:#164a47; color:#5c8a87; border-color:#164a47; }
QLineEdit,QTextEdit,QComboBox,QSpinBox { background:#0c1528; color:#e8eefc; border:1px solid #2b3c5b; border-radius:9px; padding:9px; }
QLineEdit:disabled,QComboBox:disabled { background:#0a1222; color:#5c6b86; }
QComboBox#EnigmaBox { font-size:20px; font-weight:800; padding:10px 14px; min-height:30px; }
QLineEdit#EnigmaPlug { font-size:18px; font-weight:700; padding:12px 14px; }
QCheckBox { color:#aab8d0; spacing:8px; }
QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { background:#0b1020; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#2b3c5b; border-radius:5px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""


def build_style(families):
    names = ", ".join(f if f == "sans-serif" else f'"{f}"' for f in families)
    return APP_STYLE.replace("__FONTS__", names)


def _font_dirs():
    here = Path(__file__).resolve().parent
    dirs = [here / "fonts"]
    bundle = getattr(sys, "_MEIPASS", None)  # PyInstaller
    if bundle:
        dirs.insert(0, Path(bundle) / "fonts")
    return dirs


def setup_fonts(app):
    """Load fonts from ./fonts, prefer Inter and fall back to Noto Sans (full Ukrainian coverage)."""
    for folder in _font_dirs():
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in (".ttf", ".otf", ".ttc"):
                    QFontDatabase.addApplicationFont(str(path))
    installed = set(QFontDatabase.families())
    inter = next((n for n in ("Inter", "Inter Variable") if n in installed), None)
    noto = "Noto Sans" if "Noto Sans" in installed else None
    if not inter:
        print("CryptoLab: Inter not found; put Inter-*.ttf into the 'fonts' folder or install it.", file=sys.stderr)
    if not noto:
        print("CryptoLab: Noto Sans not found; put NotoSans-*.ttf into the 'fonts' folder or install it.", file=sys.stderr)
    stack = [n for n in (inter, noto) if n] + ["Segoe UI", "Helvetica Neue", "Arial"]
    font = QFont()
    font.setFamilies(stack)
    font.setPixelSize(14)
    app.setFont(font)
    return stack + ["sans-serif"]

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

def scroll_page(page):
    """Wrap a page so tall content (Enigma settings, key panel) never gets clipped."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(page)
    return area


# ── Algorithm identifiers (internal English names; the UI translates them) ──
M_CAESAR = "Caesar"
M_ROT13 = "ROT13"
M_ATBASH = "Atbash"
M_VIGENERE = "Vigenère"
M_XOR = "Repeating-key XOR (demo)"
M_ENIGMA = "Enigma I (educational)"
M_AES = "AES-256-GCM"
M_FERNET = "Fernet"
KEYED_METHODS = (M_VIGENERE, M_XOR, M_AES, M_FERNET)
ALGO_SHORT = {M_VIGENERE: "Vigenère", M_XOR: "XOR", M_AES: "AES-256-GCM", M_FERNET: "Fernet"}
ENCRYPTION_PAGE = 1


# ── Errors with codes, so the GUI can show them in the current language ──
class CryptoError(ValueError):
    def __init__(self, code, **params):
        super().__init__(code)
        self.code = code
        self.params = params


MESSAGES = {
    "input.empty": {
        "en": "Enter some text first.",
        "uk": "Спочатку введіть текст.",
    },
    "key.empty": {
        "en": "The key is empty. Enter a key or press “Generate key”.",
        "uk": "Ключ порожній. Введіть ключ або натисніть «Згенерувати ключ».",
    },
    "key.aes.length": {
        "en": "AES-256-GCM needs a HEX key of exactly 64 characters (32 bytes). Yours has {n}.",
        "uk": "AES-256-GCM потребує HEX-ключ рівно з 64 символів (32 байти). У вашому ключі їх {n}.",
    },
    "key.aes.is_base64": {
        "en": "This looks like a Base64 key (the Fernet format). AES-256-GCM needs HEX. Press “Convert key format”.",
        "uk": "Це схоже на ключ у форматі Base64 (формат Fernet). AES-256-GCM потребує HEX. Натисніть «Перетворити формат ключа».",
    },
    "key.aes.chars": {
        "en": "An AES-256-GCM key may contain only 0–9 and a–f. Invalid character: “{ch}”.",
        "uk": "Ключ AES-256-GCM може містити лише 0–9 та a–f. Недопустимий символ: «{ch}».",
    },
    "key.fernet.is_hex": {
        "en": "This looks like a HEX key (the AES-256-GCM format). Fernet needs Base64. Press “Convert key format”.",
        "uk": "Це схоже на HEX-ключ (формат AES-256-GCM). Fernet потребує Base64. Натисніть «Перетворити формат ключа».",
    },
    "key.fernet.chars": {
        "en": "A Fernet key must be Base64. Invalid character: “{ch}”.",
        "uk": "Ключ Fernet має бути у форматі Base64. Недопустимий символ: «{ch}».",
    },
    "key.fernet.b64": {
        "en": "This is not valid Base64. A Fernet key is 44 characters long and usually ends with “=”.",
        "uk": "Це некоректний Base64. Ключ Fernet має 44 символи і зазвичай закінчується на «=».",
    },
    "key.fernet.length": {
        "en": "A Fernet key must decode to exactly 32 bytes; yours decodes to {n}. Paste the whole key or generate a new one.",
        "uk": "Ключ Fernet має декодуватися рівно в 32 байти, а ваш — у {n}. Вставте ключ повністю або згенеруйте новий.",
    },
    "key.vig.chars": {
        "en": "A Vigenère key may contain only Latin letters A–Z. Invalid character: “{ch}”.",
        "uk": "Ключ Віженера може містити лише латинські літери A–Z. Недопустимий символ: «{ch}».",
    },
    "token.bad_b64": {
        "en": "The input is not a valid Base64 token. Paste the whole token produced by encryption, without extra characters.",
        "uk": "Вхідні дані не є коректним токеном Base64. Вставте весь токен, отриманий після шифрування, без зайвих символів.",
    },
    "token.too_short": {
        "en": "The token is too short for an AES-256-GCM message; it may be cut off.",
        "uk": "Токен закороткий для повідомлення AES-256-GCM; можливо, його скопійовано не повністю.",
    },
    "token.looks_fernet": {
        "en": "This looks like a Fernet token (it starts with “gAAAA”). Select Fernet instead of AES-256-GCM.",
        "uk": "Це схоже на токен Fernet (він починається з «gAAAA»). Оберіть Fernet замість AES-256-GCM.",
    },
    "token.not_fernet": {
        "en": "This does not look like a Fernet token (they start with “gAAAA”). If it was made with AES-256-GCM, select that algorithm.",
        "uk": "Це не схоже на токен Fernet (вони починаються з «gAAAA»). Якщо його створено в AES-256-GCM, оберіть цей алгоритм.",
    },
    "decrypt.failed": {
        "en": "Decryption failed: the key is wrong, or the data was changed or damaged.",
        "uk": "Не вдалося розшифрувати: ключ неправильний або дані змінено чи пошкоджено.",
    },
    "decrypt.xor_failed": {
        "en": "Decryption produced unreadable text. Most likely the key is wrong.",
        "uk": "Після розшифрування вийшов нечитабельний текст. Найімовірніше, ключ неправильний.",
    },
    "decrypt.not_text": {
        "en": "The data was decrypted, but it is not valid UTF-8 text.",
        "uk": "Дані розшифровано, але це не коректний текст UTF-8.",
    },
    "dep.missing": {
        "en": "The “cryptography” package is required. Install it with: python3 -m pip install cryptography",
        "uk": "Потрібна бібліотека cryptography. Встановіть її: python3 -m pip install cryptography",
    },
    "enigma.rotors": {
        "en": "Choose three different rotors from I, II, III, IV, V.",
        "uk": "Оберіть три різні ротори з I, II, III, IV, V.",
    },
    "enigma.positions": {
        "en": "Start positions and ring settings must be three letters A–Z, e.g. AAA.",
        "uk": "Початкові позиції та кільця мають бути трьома літерами A–Z, наприклад AAA.",
    },
    "enigma.reflector": {
        "en": "The reflector must be B or C.",
        "uk": "Рефлектор має бути B або C.",
    },
    "enigma.plug_format": {
        "en": "Enter plugboard pairs like this: AB CD EF.",
        "uk": "Пари штекерної панелі введіть так: AB CD EF.",
    },
    "enigma.plug_dupe": {
        "en": "A letter can be used in only one plugboard pair.",
        "uk": "Літера може входити лише в одну пару штекерної панелі.",
    },
    "op.unexpected": {
        "en": "Unexpected error: {detail}",
        "uk": "Неочікувана помилка: {detail}",
    },
    # key panel: what each algorithm expects
    "hint.aes": {
        "en": "AES-256-GCM key: 64 HEX characters (32 bytes).",
        "uk": "Ключ AES-256-GCM: 64 HEX-символи (32 байти).",
    },
    "hint.fernet": {
        "en": "Fernet key: 44 Base64 characters (32 bytes).",
        "uk": "Ключ Fernet: 44 символи Base64 (32 байти).",
    },
    "hint.vig": {
        "en": "Vigenère key: Latin letters A–Z only.",
        "uk": "Ключ Віженера: лише латинські літери A–Z.",
    },
    "hint.xor": {
        "en": "XOR key: any text (UTF-8).",
        "uk": "Ключ XOR: будь-який текст (UTF-8).",
    },
    "hint.caesar": {
        "en": "Caesar uses the shift setting above. “Generate key” picks a random shift.",
        "uk": "Цезар використовує зсув, указаний вище. «Згенерувати ключ» обирає випадковий зсув.",
    },
    "hint.enigma": {
        "en": "Enigma uses the rotor, position, ring and plugboard settings above. “Generate key” randomizes them.",
        "uk": "Енігма використовує налаштування роторів, позицій, кілець і штекерної панелі вище. «Згенерувати ключ» випадково їх змінює.",
    },
    "hint.none": {
        "en": "This algorithm does not use a key.",
        "uk": "Цей алгоритм не використовує ключ.",
    },
    "ph.aes": {"en": "64 HEX characters (0–9, a–f)", "uk": "64 HEX-символи (0–9, a–f)"},
    "ph.fernet": {"en": "44 Base64 characters", "uk": "44 символи Base64"},
    "ph.vig": {"en": "Latin letters, e.g. SECRET", "uk": "Латинські літери, напр. SECRET"},
    "ph.xor": {"en": "Any text", "uk": "Будь-який текст"},
    "ph.none": {"en": "Not used", "uk": "Не використовується"},
    "ok.aes": {
        "en": "✓ Valid key: AES-256 (32 bytes, HEX)",
        "uk": "✓ Ключ коректний: AES-256 (32 байти, HEX)",
    },
    "ok.fernet": {
        "en": "✓ Valid key: Fernet (32 bytes, Base64)",
        "uk": "✓ Ключ коректний: Fernet (32 байти, Base64)",
    },
    "ok.vig": {
        "en": "✓ Valid key ({n} letters)",
        "uk": "✓ Ключ коректний ({n} літер)",
    },
    "ok.xor": {
        "en": "✓ Key accepted ({n} bytes)",
        "uk": "✓ Ключ прийнято ({n} байтів)",
    },
    "status.generated": {
        "en": "✓ A new {algo} key was generated. Save it: you need it to decrypt.",
        "uk": "✓ Згенеровано новий ключ {algo}. Збережіть його: він потрібен для розшифрування.",
    },
    "status.caesar_random": {
        "en": "✓ Random shift applied: {n}.",
        "uk": "✓ Випадковий зсув застосовано: {n}.",
    },
    "status.enigma_random": {
        "en": "✓ Random Enigma settings applied. Note them down to decrypt later.",
        "uk": "✓ Випадкові налаштування Енігми застосовано. Запишіть їх, щоб потім розшифрувати.",
    },
}


def msg(code, lang="en", **params):
    entry = MESSAGES.get(code)
    if entry is None:
        return code
    return entry.get(lang, entry["en"]).format(**params)


# ── Key formats and validation ──
HEX_CHARS = frozenset(string.hexdigits)
B64_CHARS = frozenset(string.ascii_letters + string.digits + "+/-_=")
CONVERT_CODES = frozenset({"key.aes.is_base64", "key.fernet.is_hex"})


def _compact(text):
    """Remove all whitespace (keys and tokens are often pasted with line breaks)."""
    return "".join(text.split())


def _show_char(ch):
    return "␣" if ch.isspace() else ch


def _decode_b64_key(s):
    """Decode standard or URL-safe Base64 (padding optional). Returns bytes, or None if invalid."""
    if not s or not set(s) <= B64_CHARS:
        return None
    if ("+" in s or "/" in s) and ("-" in s or "_" in s):
        return None  # the two alphabets must not be mixed
    s = s.rstrip("=")
    if "=" in s:
        return None
    std = s.replace("-", "+").replace("_", "/")
    std += "=" * (-len(std) % 4)
    try:
        return base64.b64decode(std, validate=True)
    except (binascii.Error, ValueError):
        return None


def parse_aes_key(text):
    """AES-256-GCM key: 64 HEX characters -> 32 raw bytes."""
    s = _compact(text)
    if not s:
        raise CryptoError("key.empty")
    if set(s) <= HEX_CHARS:
        if len(s) != 64:
            raise CryptoError("key.aes.length", n=len(s))
        return bytes.fromhex(s)
    raw = _decode_b64_key(s)
    if raw is not None and len(raw) == 32:
        raise CryptoError("key.aes.is_base64")
    bad = next(c for c in s if c not in HEX_CHARS)
    raise CryptoError("key.aes.chars", ch=_show_char(bad))


def parse_fernet_key(text):
    """Fernet key: Base64 of 32 bytes (URL-safe or standard alphabet) -> 32 raw bytes."""
    s = _compact(text)
    if not s:
        raise CryptoError("key.empty")
    if len(s) == 64 and set(s) <= HEX_CHARS:
        raise CryptoError("key.fernet.is_hex")
    bad = next((c for c in s if c not in B64_CHARS), None)
    if bad is not None:
        raise CryptoError("key.fernet.chars", ch=_show_char(bad))
    raw = _decode_b64_key(s)
    if raw is None:
        raise CryptoError("key.fernet.b64")
    if len(raw) != 32:
        raise CryptoError("key.fernet.length", n=len(raw))
    return raw


def parse_vigenere_key(text):
    s = text.strip()
    if not s:
        raise CryptoError("key.empty")
    for ch in s:
        if not (ch.isascii() and ch.isalpha()):
            raise CryptoError("key.vig.chars", ch=_show_char(ch))
    return s.lower()


def parse_xor_key(text):
    if not text:
        raise CryptoError("key.empty")
    return text.encode("utf-8")


def validate_key(method, text):
    """Check a key for the algorithm and return it in the form the cipher needs."""
    if method == M_AES:
        return parse_aes_key(text)
    if method == M_FERNET:
        return parse_fernet_key(text)
    if method == M_VIGENERE:
        return parse_vigenere_key(text)
    if method == M_XOR:
        return parse_xor_key(text)
    return None


def generate_key(method):
    """Create a random key in exactly the format the algorithm accepts."""
    if method == M_AES:
        return secrets.token_bytes(32).hex()
    if method == M_FERNET:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    if method == M_VIGENERE:
        return "".join(secrets.choice(string.ascii_uppercase) for _ in range(12))
    if method == M_XOR:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16))
    raise ValueError(f"{method} does not use a text key")


def detect_key_material(text):
    """Return the 32 raw bytes if the text is a 64-char HEX key or a Base64 key of 32 bytes."""
    s = _compact(text)
    if len(s) == 64 and set(s) <= HEX_CHARS:
        return bytes.fromhex(s)
    raw = _decode_b64_key(s)
    return raw if raw is not None and len(raw) == 32 else None


def convert_key(method, text):
    """Re-write a 32-byte key in the format of the selected algorithm (HEX for AES, Base64 for Fernet)."""
    raw = detect_key_material(text)
    if raw is None:
        return text
    if method == M_AES:
        return raw.hex()
    if method == M_FERNET:
        return base64.urlsafe_b64encode(raw).decode("ascii")
    return text


def random_enigma_settings():
    rng = secrets.SystemRandom()
    letters = string.ascii_uppercase
    chars = rng.sample(letters, 2 * rng.randint(6, 10))
    return {
        "rotors": rng.sample(list(ENIGMA_ROTORS), 3),
        "positions": [rng.choice(letters) for _ in range(3)],
        "rings": [rng.choice(letters) for _ in range(3)],
        "reflector": rng.choice(list(ENIGMA_REFLECTORS)),
        "plugboard": " ".join(chars[i] + chars[i + 1] for i in range(0, len(chars), 2)),
    }


# ── Modern ciphers and XOR (pure functions, no GUI) ──
def _load_cryptography():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.exceptions import InvalidTag
    except ImportError:
        raise CryptoError("dep.missing") from None
    return AESGCM, Fernet, InvalidToken, InvalidTag


def _decode_token(token_text):
    compact = _compact(token_text)
    if not compact:
        raise CryptoError("token.bad_b64")
    try:
        return base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        raise CryptoError("token.bad_b64") from None


def aes_gcm_encrypt(raw_key, text):
    AESGCM = _load_cryptography()[0]
    nonce = secrets.token_bytes(12)
    token = nonce + AESGCM(raw_key).encrypt(nonce, text.encode("utf-8"), None)
    return base64.b64encode(token).decode("ascii")


def aes_gcm_decrypt(raw_key, token_text):
    AESGCM, _, _, InvalidTag = _load_cryptography()
    if _compact(token_text).startswith("gAAAA"):
        raise CryptoError("token.looks_fernet")
    token = _decode_token(token_text)
    if len(token) < 12 + 16:  # nonce + GCM tag
        raise CryptoError("token.too_short")
    try:
        plain = AESGCM(raw_key).decrypt(token[:12], token[12:], None)
    except InvalidTag:
        raise CryptoError("decrypt.failed") from None
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError:
        raise CryptoError("decrypt.not_text") from None


def fernet_encrypt(raw_key, text):
    Fernet = _load_cryptography()[1]
    return Fernet(base64.urlsafe_b64encode(raw_key)).encrypt(text.encode("utf-8")).decode("ascii")


def fernet_decrypt(raw_key, token_text):
    _, Fernet, InvalidToken, _ = _load_cryptography()
    compact = _compact(token_text)
    if not compact.startswith("gAAAA"):
        raise CryptoError("token.not_fernet")
    try:
        plain = Fernet(base64.urlsafe_b64encode(raw_key)).decrypt(compact.encode("ascii"))
    except UnicodeEncodeError:
        raise CryptoError("token.bad_b64") from None
    except InvalidToken:
        raise CryptoError("decrypt.failed") from None
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError:
        raise CryptoError("decrypt.not_text") from None


def xor_encrypt(key, text):
    """key: bytes from parse_xor_key."""
    return base64.b64encode(xor_bytes(text.encode("utf-8"), key)).decode("ascii")


def xor_decrypt(key, token_text):
    raw = _decode_token(token_text)
    try:
        return xor_bytes(raw, key).decode("utf-8")
    except UnicodeDecodeError:
        raise CryptoError("decrypt.xor_failed") from None


def atbash(text):
    out = []
    for ch in text:
        if ch.isascii() and ch.isalpha():
            base = 65 if ch.isupper() else 97
            out.append(chr(base + 25 - (ord(ch) - base)))
        else:
            out.append(ch)
    return "".join(out)


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
        raise CryptoError("key.empty")
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
        raise CryptoError("key.empty")
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

def parse_plugboard(plugboard):
    """Turn 'AB CD EF' into a symmetric swap table. Raises CryptoError on bad input."""
    text = plugboard.upper()
    pairs = re.findall(r"[A-Z]{2}", text)
    compact = re.sub(r"[\s,;:-]", "", text)
    if len(compact) != 2 * len(pairs):
        raise CryptoError("enigma.plug_format")
    plug, used = {}, set()
    for a, b in pairs:
        if a == b or a in used or b in used:
            raise CryptoError("enigma.plug_dupe")
        used.update((a, b))
        plug[a] = b
        plug[b] = a
    return plug


#Enigma process
def enigma_transform(text, rotor_names="I II III", positions="AAA", rings="AAA", reflector="B", plugboard=""):
    """Encrypt/decrypt with a simplified three-rotor Enigma I; letters only step rotors."""
    names = rotor_names.upper().split()
    if len(names) != 3 or any(n not in ENIGMA_ROTORS for n in names) or len(set(names)) != 3:
        raise CryptoError("enigma.rotors")
    positions, rings = positions.upper(), rings.upper()
    if len(positions) != 3 or len(rings) != 3 or not positions.isalpha() or not rings.isalpha() or not positions.isascii() or not rings.isascii():
        raise CryptoError("enigma.positions")
    if reflector.upper() not in ENIGMA_REFLECTORS:
        raise CryptoError("enigma.reflector")
    plug = parse_plugboard(plugboard)

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
        "SECURITY TOOLKIT / {APP_VERSION}": "НАБІР ІНСТРУМЕНТІВ / APP_VERSION",
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
        "AES-GCM and Fernet output is a Base64 token containing the nonce/metadata and ciphertext. Manage the key in the key panel below; it is validated before every operation. Enigma I is a historical educational simulator, not secure encryption.": "Результат AES-GCM і Fernet — токен Base64 із nonce/метаданими та шифротекстом. Ключем керуйте на панелі ключів нижче: перед кожною операцією він перевіряється. Енігма I — історичний навчальний симулятор, а не надійне шифрування.",
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
        "KEY PANEL": "ПАНЕЛЬ КЛЮЧІВ",
        "Clear": "Очистити",
        "Convert key format": "Перетворити формат ключа",
        "ENIGMA SETTINGS": "НАЛАШТУВАННЯ ЕНІГМИ",
        "LEFT": "ЛІВИЙ", "MIDDLE": "СЕРЕДНІЙ", "RIGHT": "ПРАВИЙ",
        "AB CD EF (optional)": "AB CD EF (необов’язково)",
    }
}

class KeyPanel(QFrame):
    """The single key panel of the main window.

    It knows which key format every algorithm needs, generates a compatible key
    and validates the key live, before encryption and decryption."""

    STATUS_STYLES = {
        "ok": "color:#5de0bd;font-weight:700;",
        "bad": "color:#ff9b9b;font-weight:700;",
        "info": "color:#91a0bb;",
    }
    HINT_CODES = {M_AES: "hint.aes", M_FERNET: "hint.fernet", M_VIGENERE: "hint.vig",
                  M_XOR: "hint.xor", M_CAESAR: "hint.caesar", M_ENIGMA: "hint.enigma"}
    PLACEHOLDER_CODES = {M_AES: "ph.aes", M_FERNET: "ph.fernet", M_VIGENERE: "ph.vig", M_XOR: "ph.xor"}

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.method = M_CAESAR
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(8)
        lay.addWidget(label("KEY PANEL", "Eyebrow"))
        self.hint = label("", "Muted")
        lay.addWidget(self.hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.key_edit = QLineEdit()
        self.generate_btn = QPushButton("Generate key")
        self.generate_btn.setObjectName("Primary")
        self.copy_btn = QPushButton("Copy key")
        self.clear_btn = QPushButton("Clear")
        row.addWidget(self.key_edit, 1)
        for button in (self.generate_btn, self.copy_btn, self.clear_btn):
            row.addWidget(button)
        lay.addLayout(row)

        status_row = QHBoxLayout()
        self.status = label("", "Muted")
        self.convert_btn = QPushButton("Convert key format")
        self.convert_btn.setVisible(False)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.convert_btn)
        lay.addLayout(status_row)

        self.key_edit.textChanged.connect(self.refresh)
        self.generate_btn.clicked.connect(self.on_generate)
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.key_edit.text()))
        self.clear_btn.clicked.connect(self.key_edit.clear)
        self.convert_btn.clicked.connect(self.on_convert)

    def key_text(self):
        return self.key_edit.text()

    def set_key(self, text):
        self.key_edit.setText(text)

    def set_algorithm(self, method):
        self.method = method
        self.refresh()

    def flash(self, text, state="ok"):
        self.status.setText(text)
        self.status.setStyleSheet(self.STATUS_STYLES[state])

    def refresh(self, *_):
        lang = self.owner.lang
        m = self.method
        keyed = m in KEYED_METHODS
        self.hint.setText(msg(self.HINT_CODES.get(m, "hint.none"), lang))
        self.key_edit.setPlaceholderText(msg(self.PLACEHOLDER_CODES.get(m, "ph.none"), lang))
        self.key_edit.setEnabled(keyed)
        self.generate_btn.setEnabled(keyed or m in (M_CAESAR, M_ENIGMA))
        self.copy_btn.setEnabled(keyed)
        self.clear_btn.setEnabled(keyed)
        self.convert_btn.setVisible(False)
        if not keyed:
            self.flash("", "info")
            return
        text = self.key_edit.text()
        if not text.strip():
            self.flash(msg("key.empty", lang), "info")
            return
        try:
            parsed = validate_key(m, text)
        except CryptoError as exc:
            self.flash("✕ " + msg(exc.code, lang, **exc.params), "bad")
            self.convert_btn.setVisible(exc.code in CONVERT_CODES)
            return
        if m == M_AES:
            ok = msg("ok.aes", lang)
        elif m == M_FERNET:
            ok = msg("ok.fernet", lang)
        else:
            ok = msg("ok.vig" if m == M_VIGENERE else "ok.xor", lang, n=len(parsed))
        self.flash(ok, "ok")

    def on_generate(self):
        lang, m = self.owner.lang, self.method
        if m == M_CAESAR:
            shift = secrets.randbelow(25) + 1
            self.owner.caesar_shift.setValue(shift)
            self.flash(msg("status.caesar_random", lang, n=shift))
        elif m == M_ENIGMA:
            self.owner.apply_enigma_settings(random_enigma_settings())
            self.flash(msg("status.enigma_random", lang))
        elif m in KEYED_METHODS:
            self.set_key(generate_key(m))
            self.flash(msg("status.generated", lang, algo=ALGO_SHORT[m]))

    def on_convert(self):
        self.set_key(convert_key(self.method, self.key_edit.text()))


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
        side.addWidget(label(f"SECURITY TOOLKIT / {APP_VERSION}", "Eyebrow"))
        side.addSpacing(12)
        side.addWidget(label("LANGUAGE", "Eyebrow"))
        self.language_selector = QComboBox()
        self.language_selector.setObjectName("LanguageSelector")
        self.language_selector.addItems(["English", "Українська"])
        side.addWidget(self.language_selector)
        side.addSpacing(12)

        self.key_panel = KeyPanel(self)
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
            self.stack.addWidget(scroll_page(builder()))
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
        ml.addWidget(self.key_panel)
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
        self.key_panel.setVisible(index == ENCRYPTION_PAGE)

    def shell(self, eyebrow, title, desc):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(13)
        layout.addWidget(label(eyebrow, "Eyebrow"))
        layout.addWidget(label(title, "PageTitle"))
        layout.addWidget(label(desc, "Muted"))
        return page, layout

    def dashboard_page(self):
        page, layout = self.shell(f"CONTROL CENTER / {APP_VERSION}", "Welcome to CryptoLab.", "A local workspace for cryptography experiments and code inspection.")
        grid = QGridLayout()
        for i, (num, caption) in enumerate([("05", "LAB MODULES"), ("08+", "HASH OPTIONS"), (APP_VERSION, "RELEASE")]):
            box, b = card()
            b.addWidget(label(num, "Metric"))
            b.addWidget(label(caption, "Eyebrow"))
            grid.addWidget(box, 0, i)
        layout.addLayout(grid)
        box, b = card()
        b.addWidget(label(f"WHAT'S NEW IN {APP_VERSION}", "Eyebrow"))
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

    @property
    def lang(self):
        return "uk" if self.language_selector.currentIndex() == 1 else "en"

    def ui(self, text):
        """Translate a static UI string into the current language."""
        return TRANSLATIONS[self.lang].get(text, text)

    @staticmethod
    def _enigma_box(items, current):
        box = QComboBox()
        box.setObjectName("EnigmaBox")
        box.addItems(items)
        box.setCurrentText(current)
        box.setMinimumWidth(96)
        return box

    def encryption_page(self):
        page, layout = self.shell("CIPHERS / 01", "Encryption laboratory", "Choose a method. Modern encryption uses the optional cryptography package.")
        box, b = card()
        self.cipher = QComboBox()
        self.cipher.addItems([M_CAESAR, M_ROT13, M_ATBASH, M_VIGENERE, M_XOR, M_ENIGMA, M_AES, M_FERNET])
        b.addWidget(field("Algorithm"))
        b.addWidget(self.cipher)
        self.caesar_shift_label = field("Caesar shift (0–25)")
        b.addWidget(self.caesar_shift_label)
        self.caesar_shift = QSpinBox()
        self.caesar_shift.setRange(0, 25)
        self.caesar_shift.setValue(3)
        b.addWidget(self.caesar_shift)

        # Enigma: large pickers instead of free text, so wrong values cannot be typed
        self.enigma_panel = QFrame()
        self.enigma_panel.setObjectName("SubCard")
        eg = QGridLayout(self.enigma_panel)
        eg.setContentsMargins(16, 14, 16, 14)
        eg.setHorizontalSpacing(12)
        eg.setVerticalSpacing(10)
        eg.setColumnMinimumWidth(0, 200)
        for col in (1, 2, 3):
            eg.setColumnStretch(col, 1)
        eg.addWidget(field("Enigma settings"), 0, 0, 1, 4)
        for col, name in enumerate(("Left", "Middle", "Right"), start=1):
            head = field(name)
            head.setAlignment(Qt.AlignCenter)
            eg.addWidget(head, 1, col)
        letters = list(string.ascii_uppercase)
        self.enigma_rotor_boxes = [self._enigma_box(list(ENIGMA_ROTORS), d) for d in ("I", "II", "III")]
        self.enigma_pos_boxes = [self._enigma_box(letters, "A") for _ in range(3)]
        self.enigma_ring_boxes = [self._enigma_box(letters, "A") for _ in range(3)]
        rows = (("Rotors left to right (I–V)", self.enigma_rotor_boxes),
                ("Start positions (3 letters)", self.enigma_pos_boxes),
                ("Ring settings (3 letters)", self.enigma_ring_boxes))
        for row, (title, boxes) in enumerate(rows, start=2):
            eg.addWidget(field(title), row, 0)
            for col, combo in enumerate(boxes, start=1):
                eg.addWidget(combo, row, col)
        self.enigma_reflector = self._enigma_box(list(ENIGMA_REFLECTORS), "B")
        eg.addWidget(field("Reflector"), 5, 0)
        eg.addWidget(self.enigma_reflector, 5, 1)
        self.enigma_plugboard = QLineEdit()
        self.enigma_plugboard.setObjectName("EnigmaPlug")
        self.enigma_plugboard.setPlaceholderText("AB CD EF (optional)")
        eg.addWidget(field("Plugboard pairs"), 6, 0)
        eg.addWidget(self.enigma_plugboard, 6, 1, 1, 3)
        self.enigma_warn = label("", "Muted")
        self.enigma_warn.setStyleSheet("color:#ff9b9b;font-weight:700;")
        eg.addWidget(self.enigma_warn, 7, 0, 1, 4)
        for combo in self.enigma_rotor_boxes:
            combo.currentIndexChanged.connect(self.check_enigma)
        self.enigma_plugboard.textChanged.connect(self.check_enigma)
        b.addWidget(self.enigma_panel)

        self.cipher.currentTextChanged.connect(self.update_cipher_controls)
        self.update_cipher_controls(self.cipher.currentText())
        self.enc_input = QTextEdit()
        self.enc_input.setPlaceholderText("Enter text, or Base64 token when decrypting…")
        self.enc_input.setFixedHeight(115)
        b.addWidget(field("Input"))
        b.addWidget(self.enc_input)
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
        layout.addWidget(label("AES-GCM and Fernet output is a Base64 token containing the nonce/metadata and ciphertext. Manage the key in the key panel below; it is validated before every operation. Enigma I is a historical educational simulator, not secure encryption.", "Muted"))
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
        self.caesar_shift_label.setVisible(method == M_CAESAR)
        self.caesar_shift.setVisible(method == M_CAESAR)
        self.enigma_panel.setVisible(method == M_ENIGMA)
        self.key_panel.set_algorithm(method)
        self.check_enigma()

    def enigma_settings(self):
        return (
            " ".join(c.currentText() for c in self.enigma_rotor_boxes),
            "".join(c.currentText() for c in self.enigma_pos_boxes),
            "".join(c.currentText() for c in self.enigma_ring_boxes),
            self.enigma_reflector.currentText(),
            self.enigma_plugboard.text(),
        )

    def apply_enigma_settings(self, s):
        for combo, value in zip(self.enigma_rotor_boxes, s["rotors"]):
            combo.setCurrentText(value)
        for combo, value in zip(self.enigma_pos_boxes, s["positions"]):
            combo.setCurrentText(value)
        for combo, value in zip(self.enigma_ring_boxes, s["rings"]):
            combo.setCurrentText(value)
        self.enigma_reflector.setCurrentText(s["reflector"])
        self.enigma_plugboard.setText(s["plugboard"])

    def check_enigma(self, *_):
        """Live check of the Enigma settings that can still be wrong (duplicate rotors, plugboard)."""
        error = None
        if len({c.currentText() for c in self.enigma_rotor_boxes}) != 3:
            error = CryptoError("enigma.rotors")
        else:
            try:
                parse_plugboard(self.enigma_plugboard.text())
            except CryptoError as exc:
                error = exc
        self.enigma_warn.setText("⚠ " + msg(error.code, self.lang, **error.params) if error else "")
        self.enigma_warn.setVisible(error is not None)

    def run_cipher(self, encrypt):
        method = self.current_method()
        try:
            text = self.enc_input.toPlainText()
            if not text:
                raise CryptoError("input.empty")
            self.enc_output.setPlainText(self._apply_cipher(method, text, encrypt))
        except CryptoError as exc:
            self._show_error(msg(exc.code, self.lang, **exc.params))
        except Exception as exc:
            self._show_error(msg("op.unexpected", self.lang, detail=str(exc) or exc.__class__.__name__))

    def current_method(self):
        return self.canonical_text(self.cipher.currentText())

    def _show_error(self, text):
        self.enc_output.clear()  # never leave a stale result next to an error
        QMessageBox.warning(self, self.ui("Operation failed"), text)

    def _apply_cipher(self, method, text, encrypt):
        if method == M_CAESAR:
            return caesar(text, self.caesar_shift.value() * (1 if encrypt else -1))
        if method == M_ROT13:
            return caesar(text, 13)
        if method == M_ATBASH:
            return atbash(text)
        if method == M_ENIGMA:
            return enigma_transform(text, *self.enigma_settings())

        # Keyed algorithms: the key is validated here, before anything is encrypted or decrypted.
        if encrypt and not self.key_panel.key_text().strip():
            self.key_panel.on_generate()  # no key typed: create a compatible one and show it
        key = validate_key(method, self.key_panel.key_text())
        if method == M_VIGENERE:
            return vigenere(text, key, not encrypt)
        if method == M_XOR:
            return xor_encrypt(key, text) if encrypt else xor_decrypt(key, text)
        if method == M_AES:
            return aes_gcm_encrypt(key, text) if encrypt else aes_gcm_decrypt(key, text)
        if method == M_FERNET:
            return fernet_encrypt(key, text) if encrypt else fernet_decrypt(key, text)
        raise CryptoError("op.unexpected", detail=method)

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
    families = setup_fonts(app)
    app.setStyleSheet(build_style(families))
    window = CryptoLab()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()