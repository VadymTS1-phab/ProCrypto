"""Lightweight JSON-based localization for CryptoLab Pro.

Every language is one file: translations/<code>.json

    {
      "meta":     {"code": "uk", "name": "Українська", "order": 1},
      "ui":       {"<English source text>": "<translation>", ...},
      "messages": {"<message.code>": "<text with {placeholders}>", ...}
    }

* "ui" is keyed by the English text that appears in the interface. A missing
  key simply falls back to the English text, so the app never breaks.
* "messages" holds texts produced by the code (errors, hints, dialogs).
  They are addressed by code and may contain {placeholders}.

To add a language: copy en.json to <code>.json, translate the values, set "meta".
It appears in the language selector automatically. Run `python i18n.py` to check
that nothing is missing.
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_LANGUAGE = "en"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _translations_dir():
    here = Path(__file__).resolve().parent
    candidates = [here / "translations"]
    bundle = getattr(sys, "_MEIPASS", None)  # PyInstaller
    if bundle:
        candidates.insert(0, Path(bundle) / "translations")
    return next((p for p in candidates if p.is_dir()), candidates[-1])


class I18n:
    def __init__(self, directory=None, language=DEFAULT_LANGUAGE):
        self.directory = Path(directory) if directory else _translations_dir()
        self.catalogs = {}
        self.language = DEFAULT_LANGUAGE
        self.load()
        self.set_language(language)

    # ── loading ──
    def load(self):
        self.catalogs.clear()
        if not self.directory.is_dir():
            print(f"i18n: translations folder not found: {self.directory}", file=sys.stderr)
            return
        for path in sorted(self.directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                ui, messages, meta = data.get("ui", {}), data.get("messages", {}), data.get("meta", {})
                if not all(isinstance(x, dict) for x in (ui, messages, meta)):
                    raise ValueError("'meta', 'ui' and 'messages' must be objects")
            except (OSError, ValueError) as exc:  # includes json.JSONDecodeError
                print(f"i18n: skipped {path.name}: {exc}", file=sys.stderr)
                continue
            self.catalogs[path.stem] = {
                "name": str(meta.get("name", path.stem)),
                "order": meta.get("order", 99),
                "ui": ui,
                "messages": messages,
            }

    @property
    def codes(self):
        """Language codes in display order (English first)."""
        return sorted(self.catalogs, key=lambda c: (self.catalogs[c]["order"], c))

    @property
    def names(self):
        """Native language names, in the same order as `codes`."""
        return [self.catalogs[c]["name"] for c in self.codes]

    def set_language(self, code):
        if code in self.catalogs:
            self.language = code
            return True
        return False

    # ── lookups ──
    def _lookup(self, section, key):
        for code in (self.language, DEFAULT_LANGUAGE):
            value = self.catalogs.get(code, {}).get(section, {}).get(key)
            if isinstance(value, str):
                return value
        return None

    def tr(self, text):
        """Translate an interface string (the English text is the key)."""
        value = self._lookup("ui", text)
        return text if value is None else value

    def msg(self, code, **params):
        """Return a message by code with {placeholders} filled in."""
        text = self._lookup("messages", code)
        if text is None:
            return code
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            return text

    # ── translation QA ──
    def audit(self):
        """Compare every language with English. Returns {code: [problems]}."""
        base = self.catalogs.get(DEFAULT_LANGUAGE)
        report = {}
        if base is None:
            return {DEFAULT_LANGUAGE: ["en.json is missing or invalid"]}
        for code in self.codes:
            if code == DEFAULT_LANGUAGE:
                continue
            problems = []
            cat = self.catalogs[code]
            for section in ("ui", "messages"):
                for key, source in base[section].items():
                    if key not in cat[section]:
                        problems.append(f"missing {section}: {key[:60]!r}")
                    elif set(_PLACEHOLDER.findall(source)) != set(_PLACEHOLDER.findall(str(cat[section][key]))):
                        problems.append(f"placeholder mismatch in {section}: {key[:60]!r}")
                for key in cat[section]:
                    if key not in base[section]:
                        problems.append(f"unknown {section} key (not in en.json): {key[:60]!r}")
            report[code] = problems
        return report


def main():
    """`python i18n.py` prints a completeness report for all languages."""
    i18n = I18n()
    print("Languages:", ", ".join(f"{c} ({n})" for c, n in zip(i18n.codes, i18n.names)) or "none")
    report = i18n.audit()
    bad = False
    for code, problems in report.items():
        if problems:
            bad = True
            print(f"\n{code}: {len(problems)} problem(s)")
            for line in problems:
                print("  -", line)
        else:
            print(f"{code}: OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
