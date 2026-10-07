"""Static, plain-language help content for the victim support centre.

IMPORTANT: have your team (and legal/policing advisers) review this text before real use.
It deliberately avoids legal advice, legal time limits, and promises about recovery.
"""

CONSENT_VERSION = "2026-10-v1"

CONSENT_NOTICE = {
    "version": CONSENT_VERSION,
    "purpose": (
        "We use the details you give us only to help an investigator understand and trace your "
        "complaint about a crypto fraud."
    ),
    "who_can_see": (
        "Only authorised investigators assigned to your complaint. Other victims cannot see "
        "your information. We log every time an investigator opens your details and show you that log."
    ),
    "retention": (
        "Your complaint is kept for as long as it is needed for the investigation and as required "
        "by law. [TEAM TO CONFIRM exact retention period with legal/policy before launch.]"
    ),
    "never_share": "We will never ask for your seed phrase, private keys, passwords, OTPs or Aadhaar number.",
}

SUPPORT = {
    "safe_handling_banner": (
        "Never share your seed phrase, private keys, passwords, OTPs or Aadhaar number with anyone, "
        "including us. No genuine investigator will ask for them."
    ),
    "recovery_scam_warning": (
        "Be careful of anyone who contacts you offering to recover your lost crypto for a fee. These "
        "are very often a second scam. Do not pay anyone, and do not click links they send."
    ),
    "report_officially": (
        "If you have not already, also report on cybercrime.gov.in or call the national "
        "cybercrime helpline 1930 as soon as possible."
    ),
    "secure_accounts": [
        "Change the passwords of your email, exchange and wallet apps from a device you trust.",
        "Turn on two-factor authentication on your email and exchange accounts.",
        "If you shared a seed phrase or private key, move any remaining funds to a brand new wallet.",
        "Stop all contact with the scammer, but keep every message and screenshot as evidence.",
        "Do not share OTPs with anyone who calls or messages you.",
    ],
    "bank_upi_steps": [
        "If money left through a bank or UPI, contact your bank straight away using the number on "
        "your card or the official app.",
        "Tell them it is a fraud and note the complaint or reference number they give you.",
        "Keep the transaction ID, date, time and amount ready.",
    ],
    "what_happens_next": {
        "steps": [
            "Your complaint is received and an officer reviews it.",
            "An officer verifies the details you gave.",
            "The investigation team follows the movement of funds.",
            "If something more is needed from you, it appears under 'What we need from you'.",
        ],
        "freezing_can": (
            "Where funds reach a regulated service, authorities may be able to ask that service to "
            "hold them while they investigate."
        ),
        "freezing_cannot": (
            "Freezing is not guaranteed. Funds may already have moved, and some services or wallets "
            "cannot be frozen. We cannot promise that money will be recovered or how long it takes."
        ),
    },
    "sextortion": {
        "message": (
            "If someone is threatening to share private images of you: you are not to blame. Do not "
            "pay, keep the messages, and report it. You can mark any file you upload as 'restricted' "
            "so it is not previewed."
        ),
        "mental_health_helpline": "Tele-MANAS 14416 (free mental health support)",
    },
    "glossary": {
        "Wallet address": "A long code that identifies where crypto is held, like an account number.",
        "Transaction hash": "A unique ID for one transfer, like a receipt number.",
        "Exchange": "A company where people buy, sell and hold crypto.",
        "Seed phrase": "12 or 24 secret words that give full control of a wallet. Never share it.",
        "Private key": "A secret code that lets someone move the crypto in a wallet. Never share it.",
        "Freezing": "A request to a service to hold funds while authorities investigate.",
    },
}

STAGES = [
    ("received", "Received"),
    ("verified", "Verified by officer"),
    ("in_progress", "Investigation in progress"),
    ("with_officer", "With officer"),
    ("action_taken", "Action taken"),
    ("closed", "Closed"),
]
STAGE_LABEL = dict(STAGES)
STAGE_LABEL["draft"] = "Draft"
STAGE_LABEL["submitted"] = "Complaint Submitted"
STAGE_LABEL["under_verification"] = "Under Verification"

NEXT_STEPS_AFTER_SUBMIT = [
    "Keep your acknowledgement ID safe. It is the only reference we will use with you.",
    "If you have not already, also report on cybercrime.gov.in or call 1930.",
    "You can add screenshots and receipts under Evidence at any time.",
    "We will only ever send you a short message saying 'Your case has an update'.",
]
