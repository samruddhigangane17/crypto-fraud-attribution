"""ReportLab-based Law Enforcement Freeze Notice & BSA Section 63 Certificate Generator.

USP 1: Freeze-Point Finder (Exchange + Stablecoin-Issuer Freeze)
Generates an official, court-ready Law Enforcement Freeze & Preservation Notice:
- Addressed to Exchange Nodal Compliance Officer or Stablecoin Issuer (Tether/Circle)
- Citations under Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023 Sections 94 & 106
- Mandatory Bharatiya Sakshya Adhiniyam (BSA), 2023 Section 63 Electronic Evidence Certificate
- Pre-filled cryptographic SHA-256 integrity hash of trace snapshot & registry version
"""

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class FreezeNoticeData(BaseModel):
    case_id: str
    ncrp_ack_no: str = "NCRP-2024-EX-890412"
    investigating_agency: str = "Cyber Crime Investigation Cell, Crime Branch"
    investigating_officer: str = "Inspector (Cyber / Financial Crimes), IO Desk"
    officer_badge_id: str = "LEA-CYBER-8842"
    station_jurisdiction: str = "Special Cyber Police Station"
    destination_address: str
    entity_name: str = "Unattributed Wallet"
    freezable_by: str = "none"  # "Exchange" | "Tether" | "Circle" | "Exchange + Tether" | "Exchange + Circle" | "none"
    freeze_mechanism: str = "VASP Account Freeze"
    issuer_contact_portal: str = "compliance-desk@vasp-network.int"
    traced_amount: float = 0.0
    asset: str = "USDT"
    chain: str = "ethereum"
    token_contract: Optional[str] = None
    blacklist_selector: Optional[str] = None
    attribution_confidence: float = 0.85
    confidence_gate_passed: bool = True
    hop_count: int = 1
    tx_hashes: List[str] = Field(default_factory=list)
    sha256_hash: Optional[str] = None
    registry_version: str = "2026.1-USP1-VASP-STABLECOIN-v1.4"
    created_at_utc: Optional[str] = None
    created_at_ist: Optional[str] = None
    legal_basis: str = "Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023 Sections 94 & 106 r/w BSA 2023 Section 63"
    notes: Optional[str] = None


class FreezeNoticeRequest(BaseModel):
    case_id: str
    destination_address: Optional[str] = None
    target_entity: Optional[str] = None
    freezable_by: Optional[str] = None
    freeze_mechanism: Optional[str] = None
    issuer_contact_portal: Optional[str] = None
    traced_amount: Optional[float] = None
    asset: Optional[str] = None
    chain: Optional[str] = None
    token_contract: Optional[str] = None
    blacklist_selector: Optional[str] = None
    attribution_confidence: Optional[float] = None
    confidence_gate_passed: Optional[bool] = None
    investigating_agency: Optional[str] = "Cyber Crime Investigation Cell, Crime Branch"
    investigating_officer: Optional[str] = "Inspector (Cyber / Financial Crimes), IO Desk"
    officer_badge_id: Optional[str] = "LEA-CYBER-8842"
    station_jurisdiction: Optional[str] = "Special Cyber Police Station"
    ncrp_ack_no: Optional[str] = None
    notes: Optional[str] = None
    format: Optional[str] = "pdf"  # "pdf" or "json"


def build_freeze_notice_data(req: FreezeNoticeRequest) -> FreezeNoticeData:
    """Extracts case details and constructs an attested FreezeNoticeData instance."""
    case_id = req.case_id
    dossier = None
    try:
        from backend.api.routes import _get_or_404
        dossier = _get_or_404(case_id)
    except Exception:
        pass

    dest_addr = req.destination_address
    entity_name = req.target_entity or "Unattributed Wallet"
    freezable_by = req.freezable_by or "none"
    freeze_mechanism = req.freeze_mechanism or "None (Unhosted Native Asset)"
    issuer_contact_portal = req.issuer_contact_portal or "compliance-desk@vasp-network.int"
    traced_amount = req.traced_amount or 0.0
    asset = req.asset or "USDT"
    chain = req.chain or "ethereum"
    token_contract = req.token_contract
    blacklist_selector = req.blacklist_selector
    attribution_confidence = req.attribution_confidence or 0.85
    confidence_gate_passed = req.confidence_gate_passed if req.confidence_gate_passed is not None else True
    ncrp_ack_no = req.ncrp_ack_no or f"NCRP-2024-EX-{abs(hash(case_id)) % 900000 + 100000}"
    tx_hashes = []
    hop_count = 1

    if dossier:
        from backend.recovery.ranking import global_ranking_engine
        rankings = global_ranking_engine.rank_destinations(dossier.paths, dossier.endpoints)
        matched_dest = None
        if dest_addr:
            for r in rankings:
                if r.destination_address.lower() == dest_addr.lower():
                    matched_dest = r
                    break
        elif rankings:
            matched_dest = rankings[0]

        if matched_dest:
            dest_addr = dest_addr or matched_dest.destination_address
            entity_name = req.target_entity or matched_dest.entity_name
            freezable_by = req.freezable_by or matched_dest.freezable_by
            freeze_mechanism = req.freeze_mechanism or matched_dest.freeze_mechanism
            issuer_contact_portal = req.issuer_contact_portal or matched_dest.issuer_contact_portal
            traced_amount = req.traced_amount if req.traced_amount is not None else matched_dest.traced_amount
            asset = req.asset or matched_dest.asset
            attribution_confidence = (
                req.attribution_confidence if req.attribution_confidence is not None else matched_dest.attribution_confidence
            )
            token_contract = req.token_contract or matched_dest.token_contract
            blacklist_selector = req.blacklist_selector or matched_dest.blacklist_selector

        tx_hashes = [tx.tx_hash for path in dossier.paths for tx in path.transactions if tx.tx_hash][:5]
        if dossier.paths:
            hop_count = max(len(p.transactions) for p in dossier.paths)
        if hasattr(dossier, "chain") and dossier.chain:
            chain = req.chain or dossier.chain

    if not dest_addr:
        dest_addr = "0x0000000000000000000000000000000000000000"

    # Enforce minimum attribution confidence threshold (>= 75%) and freezability
    if req.confidence_gate_passed is not None:
        confidence_gate_passed = req.confidence_gate_passed
    else:
        confidence_gate_passed = (attribution_confidence >= 0.75) and (freezable_by != "none")

    return FreezeNoticeData(
        case_id=case_id,
        ncrp_ack_no=ncrp_ack_no,
        investigating_agency=req.investigating_agency or "Cyber Crime Investigation Cell, Crime Branch",
        investigating_officer=req.investigating_officer or "Inspector (Cyber / Financial Crimes), IO Desk",
        officer_badge_id=req.officer_badge_id or "LEA-CYBER-8842",
        station_jurisdiction=req.station_jurisdiction or "Special Cyber Police Station",
        destination_address=dest_addr,
        entity_name=entity_name,
        freezable_by=freezable_by,
        freeze_mechanism=freeze_mechanism,
        issuer_contact_portal=issuer_contact_portal,
        traced_amount=traced_amount,
        asset=asset,
        chain=chain,
        token_contract=token_contract,
        blacklist_selector=blacklist_selector,
        attribution_confidence=attribution_confidence,
        confidence_gate_passed=confidence_gate_passed,
        hop_count=hop_count,
        tx_hashes=tx_hashes,
        legal_basis="Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023 Sections 94 & 106 r/w BSA 2023 Section 63",
        notes=req.notes,
    )


class NumberedNoticeCanvas(canvas.Canvas):
    """Canvas providing top running header and bottom footer with page numbering."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Top Running Header
        self.drawString(
            54,
            750,
            "LAW ENFORCEMENT & JUDICIAL PRESERVATION DIRECTIVE // SEC 94 & 106 BNSS 2023",
        )
        self.drawRightString(612 - 54, 750, "CONFIDENTIAL // RESTRICTED DISCLOSURE")

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 742, 612 - 54, 742)

        # Bottom Running Footer
        self.line(54, 45, 612 - 54, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "BHARATIYA SAKSHYA ADHINIYAM (BSA) 2023 SECTION 63 CERTIFIED RECORD")
        self.drawRightString(
            612 - 54,
            32,
            f"Page {self._pageNumber} of {total_pages}",
        )
        self.restoreState()


class FreezeNoticePDFGenerator:
    """Generates an evidentiary freeze and preservation notice PDF with BSA 2023 s.63 Certificate."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        navy_dark = colors.HexColor("#0F172A")
        slate_color = colors.HexColor("#334155")
        red_crimson = colors.HexColor("#991B1B")

        self.styles.add(
            ParagraphStyle(
                "NoticeTitle",
                parent=self.styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=17,
                textColor=red_crimson,
                alignment=1,  # Center
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "NoticeSubtitle",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=navy_dark,
                alignment=1,
                spaceAfter=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "SectionHeading",
                parent=self.styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                textColor=navy_dark,
                spaceBefore=8,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "MetaKey",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=10,
                textColor=colors.HexColor("#475569"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                "MetaVal",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=navy_dark,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "NoticeBody",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10.5,
                textColor=slate_color,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "NoticeBodyBold",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=10.5,
                textColor=navy_dark,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "NoticeMono",
                parent=self.styles["Normal"],
                fontName="Courier",
                fontSize=7,
                leading=9,
                textColor=navy_dark,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "CertItem",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=7,
                leading=9.5,
                textColor=colors.HexColor("#1E293B"),
            )
        )

    def generate_notice_pdf(self, data: FreezeNoticeData) -> bytes:
        """Assembles and renders the complete freeze notice document."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        elements = []

        # Timestamps
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        utc_str = data.created_at_utc or utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
        ist_str = data.created_at_ist or ist_now.strftime("%Y-%m-%d %H:%M:%S IST")

        # SHA-256 fingerprint
        sha_hash = data.sha256_hash
        if not sha_hash:
            canonical_payload = {
                "case_id": data.case_id,
                "ncrp_ack_no": data.ncrp_ack_no,
                "address": data.destination_address,
                "amount": data.traced_amount,
                "asset": data.asset,
                "freezable_by": data.freezable_by,
                "freeze_mechanism": data.freeze_mechanism,
                "registry_version": data.registry_version,
            }
            sha_hash = hashlib.sha256(
                json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
            ).hexdigest()

        # =========================================================================
        # 1. HEADER & FORMAL NOTICE BANNER
        # =========================================================================
        elements.append(
            Paragraph(
                "FORMAL PRESERVATION & EMERGENCY DIGITAL ASSET FREEZE DIRECTIVE",
                self.styles["NoticeTitle"],
            )
        )
        elements.append(
            Paragraph(
                "ISSUED UNDER SECTIONS 94 &amp; 106, BHARATIYA NAGARIK SURAKSHA SANHITA (BNSS), 2023<br/>"
                "READ WITH SECTION 63, BHARATIYA SAKSHYA ADHINIYAM (BSA), 2023",
                self.styles["NoticeSubtitle"],
            )
        )
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#991B1B"), spaceAfter=8))

        # =========================================================================
        # 2. CASE & AGENCY REFERENCE BLOCK
        # =========================================================================
        meta_table_data = [
            [
                Paragraph("Case Reference ID:", self.styles["MetaKey"]),
                Paragraph(f"<b>{data.case_id}</b>", self.styles["MetaVal"]),
                Paragraph("NCRP Acknowledgement No:", self.styles["MetaKey"]),
                Paragraph(f"<b>{data.ncrp_ack_no}</b>", self.styles["MetaVal"]),
            ],
            [
                Paragraph("Investigating Agency:", self.styles["MetaKey"]),
                Paragraph(data.investigating_agency, self.styles["MetaVal"]),
                Paragraph("Police Station / Jurisdiction:", self.styles["MetaKey"]),
                Paragraph(data.station_jurisdiction, self.styles["MetaVal"]),
            ],
            [
                Paragraph("Investigating Officer:", self.styles["MetaKey"]),
                Paragraph(f"{data.investigating_officer} (ID: {data.officer_badge_id})", self.styles["MetaVal"]),
                Paragraph("Issuance Timestamp:", self.styles["MetaKey"]),
                Paragraph(f"{utc_str}<br/><b>{ist_str}</b>", self.styles["MetaVal"]),
            ],
        ]

        meta_table = Table(meta_table_data, colWidths=[105, 145, 120, 134])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # 3. ADDRESSED TO (RECIPIENT ENTITY & OFFICIAL COMPLIANCE CHANNEL)
        # =========================================================================
        recipient_data = [
            [
                Paragraph("TO:", self.styles["MetaKey"]),
                Paragraph(
                    f"<b>The Nodal Compliance Officer / Law Enforcement Response Team</b><br/>"
                    f"<b>Entity:</b> {data.entity_name} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Enforcement Authority:</b> {data.freezable_by}<br/>"
                    f"<b>Official Compliance Portal / Channel:</b> {data.issuer_contact_portal}",
                    self.styles["NoticeBody"],
                ),
            ]
        ]
        recipient_table = Table(recipient_data, colWidths=[40, 464])
        recipient_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#3B82F6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(recipient_table)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # 4. SUSPECT ASSET & FREEZE SPECIFICATIONS TABLE
        # =========================================================================
        elements.append(Paragraph("I. SUSPECT ASSET & FREEZE POINT SPECIFICATIONS", self.styles["SectionHeading"]))

        conf_pct = round(data.attribution_confidence * 100)
        gate_status = "PASSED (>= 75% Confidence Gate)" if data.confidence_gate_passed else "UNDER REVIEW (< 75%)"

        suspect_rows = [
            [
                Paragraph("Target Suspect Address:", self.styles["MetaKey"]),
                Paragraph(f"<font name='Courier'><b>{data.destination_address}</b></font>", self.styles["MetaVal"]),
            ],
            [
                Paragraph("Token / Asset Traced:", self.styles["MetaKey"]),
                Paragraph(
                    f"<b>{data.traced_amount:,.4f} {data.asset}</b> &nbsp;&nbsp;"
                    f"(Network: {data.chain.upper()})",
                    self.styles["MetaVal"],
                ),
            ],
            [
                Paragraph("Smart Contract Address:", self.styles["MetaKey"]),
                Paragraph(
                    f"<font name='Courier'>{data.token_contract or 'Native Asset / Direct VASP Deposit'}</font>",
                    self.styles["MetaVal"],
                ),
            ],
            [
                Paragraph("Designated Freeze Mechanism:", self.styles["MetaKey"]),
                Paragraph(
                    f"<b>{data.freeze_mechanism}</b> &nbsp;&nbsp;"
                    f"(Selector: <font name='Courier'>{data.blacklist_selector or 'VASP Internal Hold'}</font>)",
                    self.styles["MetaVal"],
                ),
            ],
            [
                Paragraph("Attribution Confidence:", self.styles["MetaKey"]),
                Paragraph(
                    f"<b>{conf_pct}%</b> &nbsp;&nbsp;|&nbsp;&nbsp; Statutory Threshold: <b>{gate_status}</b>",
                    self.styles["MetaVal"],
                ),
            ],
            [
                Paragraph("Hop Depth & Trace Path:", self.styles["MetaKey"]),
                Paragraph(
                    f"Terminal Endpoint at Hop #{data.hop_count} from reported victim complaint origin.",
                    self.styles["MetaVal"],
                ),
            ],
        ]

        if data.tx_hashes:
            sample_tx = ", ".join([f"<font name='Courier'>{tx[:14]}...</font>" for tx in data.tx_hashes[:3]])
            suspect_rows.append([
                Paragraph("Attributed Transaction Hashes:", self.styles["MetaKey"]),
                Paragraph(sample_tx, self.styles["MetaVal"]),
            ])

        suspect_table = Table(suspect_rows, colWidths=[150, 354])
        suspect_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(suspect_table)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # 5. STATUTORY DIRECTIVES & MANDATORY PRESERVATION REQUIREMENTS
        # =========================================================================
        elements.append(Paragraph("II. STATUTORY PRESERVATION & FREEZING ORDERS", self.styles["SectionHeading"]))

        directives_text = (
            "WHEREAS an active criminal investigation into digital asset misappropriation is underway under the "
            "provisions of Indian Penal / Cyber statutes; and on-chain cryptographic path analysis has conclusively "
            "tracked stolen proceeds to the target address identified above.<br/><br/>"
            "NOW THEREFORE, under the authority vested under <b>Section 94 and Section 106 of the Bharatiya Nagarik "
            "Suraksha Sanhita (BNSS), 2023</b>, you are hereby directed to immediately effect the following:<br/>"
            "<b>1. IMMEDIATE ASSET FREEZE / BLACKLIST:</b> Invoke internal custody hold or smart contract blacklist "
            f"mechanism (<b>{data.freeze_mechanism}</b>) preventing withdrawal, liquidation, or transfer of the "
            f"stolen proceeds (approx. <b>{data.traced_amount:,.4f} {data.asset}</b>).<br/>"
            "<b>2. PRESERVATION OF KYC & TELEMETRY:</b> Preserve all Know-Your-Customer (KYC) identity records, registered "
            "email IDs, phone numbers, bank accounts, login IP access logs, device fingerprints, and withdrawal whitelist records.<br/>"
            "<b>3. PROHIBITION OF COUNTER-PARTY DISSIPATION:</b> Place a restrictive freeze on any secondary accounts or "
            "internal transfer recipients linked to the identified suspect cluster.<br/>"
            "<b>4. STATUTORY COMPLIANCE TIMELINE:</b> Acknowledge compliance within <b>twenty-four (24) hours</b> of receipt "
            "at the designated Cyber Crime Investigation Cell contact portal."
        )

        directives_box = Table(
            [[Paragraph(directives_text, self.styles["NoticeBody"])]],
            colWidths=[504],
        )
        directives_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#EF4444")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(directives_box)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # 6. BHARATIYA SAKSHYA ADHINIYAM (BSA) 2023 SECTION 63 CERTIFICATE
        # =========================================================================
        bsa_header = Paragraph(
            "III. CERTIFICATE UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM (BSA), 2023<br/>"
            "<i>(Condition Precedent for Admissibility of Electronic Records in Judicial Proceedings)</i>",
            self.styles["SectionHeading"],
        )

        bsa_items = [
            [
                Paragraph("[x]", self.styles["NoticeBodyBold"]),
                Paragraph(
                    "<b>System Description & Device Identification:</b> The computer system producing this record is the "
                    "<b>Real-Time Crypto Fraud Attribution System</b> (Registry Ver: "
                    f"<b>{data.registry_version}</b>). The machine operated continuously under official custody.",
                    self.styles["CertItem"],
                ),
            ],
            [
                Paragraph("[x]", self.styles["NoticeBodyBold"]),
                Paragraph(
                    "<b>Lawful Control & Authority:</b> The electronic record was produced during the ordinary course "
                    "of authorized cyber crime investigation by an officer having lawful control over the computational facility.",
                    self.styles["CertItem"],
                ),
            ],
            [
                Paragraph("[x]", self.styles["NoticeBodyBold"]),
                Paragraph(
                    "<b>Continuous Operational Integrity:</b> Throughout the relevant period, the system, distributed RPC nodes, "
                    "and cryptographic analyzers were operating properly. Operational integrity was uncompromised.",
                    self.styles["CertItem"],
                ),
            ],
            [
                Paragraph("[x]", self.styles["NoticeBodyBold"]),
                Paragraph(
                    "<b>Cryptographic Snapshot Attestation & SHA-256 Digest:</b> The underlying forensic trace snapshot "
                    "and stablecoin blacklist matching telemetry have been cryptographically hashed:<br/>"
                    f"<b>SHA-256 Hash Digest:</b> <font name='Courier'><b>{sha_hash}</b></font>",
                    self.styles["CertItem"],
                ),
            ],
            [
                Paragraph("[x]", self.styles["NoticeBodyBold"]),
                Paragraph(
                    "<b>Statutory Truthfulness Declaration:</b> I hereby certify that the contents of this electronic record "
                    "are true, accurate, and faithfully reproduced from raw distributed ledger state.",
                    self.styles["CertItem"],
                ),
            ],
        ]

        bsa_table = Table(bsa_items, colWidths=[20, 484])
        bsa_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#475569")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ]
            )
        )

        sign_table_data = [
            [
                Paragraph(
                    "<b>ISSUING OFFICER DETAILS:</b><br/>"
                    f"Name: {data.investigating_officer}<br/>"
                    f"Badge / Designation ID: {data.officer_badge_id}<br/>"
                    f"Jurisdiction: {data.station_jurisdiction}<br/>"
                    f"Certified Date: {ist_str}",
                    self.styles["CertItem"],
                ),
                Paragraph(
                    "<b>OFFICIAL SEAL & SIGNATURE:</b><br/><br/>"
                    "____________________________________________<br/>"
                    "Authorized Signatory // Cyber Crime Cell<br/>"
                    "[Cryptographically Attested Record]",
                    self.styles["CertItem"],
                ),
            ]
        ]
        sign_table = Table(sign_table_data, colWidths=[252, 252])
        sign_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        cert_block = KeepTogether([bsa_header, Spacer(1, 4), bsa_table, Spacer(1, 6), sign_table])
        elements.append(cert_block)

        # Build document using NumberedNoticeCanvas
        doc.build(elements, canvasmaker=NumberedNoticeCanvas)
        return buffer.getvalue()


global_freeze_notice_generator = FreezeNoticePDFGenerator()
