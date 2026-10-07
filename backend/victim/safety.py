"""Input safety for the victim portal.

Victims must never send us seed phrases, private keys, passwords, OTPs or Aadhaar numbers.
`check_text` returns a short reason code (or None). It NEVER returns, logs or echoes the text.
"""

import re
from typing import Optional

SEED_PHRASE = "seed_phrase"
PRIVATE_KEY = "private_key"
PASSWORD = "password"
OTP_VALUE = "otp"
AADHAAR = "aadhaar"

# Very common English words. A real seed phrase (BIP-39 words) almost never contains these,
# while ordinary sentences are full of them.
_COMMON = frozenset(
    """the and for you your are was were with that this have has had not but they them their then
    than from into out our his her she him its who what when where why how can could would should
    will just all any some one two been being did does done get got let him via per also very more
    most much many such only over after before again about above below under off own same too yes
    say said tell told ask asked sent send give gave take took made make went come came use used
    like want need know see saw look back there here now still even ever never because while
    which these those other another each both few new old""".split()
)

_TOKEN_OK = re.compile(r"^[a-z]{3,8}$")
_NUMBERING = re.compile(r"^\d{1,2}[.):,-]?$")

_XPRV = re.compile(r"\bxprv[1-9A-HJ-NP-Za-km-z]{100,}\b")
_WIF = re.compile(r"\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b")
_LABELLED_KEY = re.compile(r"private\s*key\s*(is|:|=)?\s*(0x)?[0-9a-fA-F]{64}\b", re.IGNORECASE)
_AADHAAR_SPACED = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b")
_AADHAAR_LABELLED = re.compile(r"aadh?a+r\D{0,12}\d{12}\b", re.IGNORECASE)
_OTP_LABELLED = re.compile(r"\botp\b\W{0,4}\d{4,8}\b", re.IGNORECASE)
_PASSWORD_LABELLED = re.compile(r"\b(password|passcode|pin)\s*(is|:|=)\s*\S+", re.IGNORECASE)

USER_MESSAGE = (
    "For your safety we cannot accept seed phrases, private keys, passwords, OTPs or Aadhaar "
    "numbers. Please remove them and try again. We will never ask you for these."
)


def looks_like_seed_phrase(text: str) -> bool:
    """True if the text has a run of 12+ plain lowercase words that are not ordinary prose."""
    run: list[str] = []
    for raw in text.split():
        if _NUMBERING.match(raw):  # "1." "2)" style numbering inside a pasted list
            continue
        token = raw if _TOKEN_OK.match(raw) else raw.lower() if _TOKEN_OK.match(raw.lower()) else None
        if token is None:
            if _is_seed_run(run):
                return True
            run = []
            continue
        run.append(token.lower())
    return _is_seed_run(run)


def _is_seed_run(run: list[str]) -> bool:
    if len(run) < 12:
        return False
    common = sum(1 for w in run if w in _COMMON)
    return common / len(run) <= 0.2


def check_text(text: Optional[str]) -> Optional[str]:
    """Return a reason code if `text` contains something we must not accept, else None."""
    if not text:
        return None
    if _XPRV.search(text) or _WIF.search(text) or _LABELLED_KEY.search(text):
        return PRIVATE_KEY
    if looks_like_seed_phrase(text):
        return SEED_PHRASE
    if _AADHAAR_SPACED.search(text) or _AADHAAR_LABELLED.search(text):
        return AADHAAR
    if _OTP_LABELLED.search(text):
        return OTP_VALUE
    if _PASSWORD_LABELLED.search(text):
        return PASSWORD
    return None
