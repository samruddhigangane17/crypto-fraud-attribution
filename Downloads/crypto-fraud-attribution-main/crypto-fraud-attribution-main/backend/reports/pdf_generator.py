"""ReportLab-based PDF evidence report generator.

Produces structured, investigator-ready forensic reports detailing multi-hop
paths, exchange/VASP attributions, explainable risk factors, confidence
assessments, alerts, and legal disclaimers.
"""

from datetime import datetime, timezone
import io
import os
from typing import List, Optional
import uuid

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

from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.monitoring import Alert
from backend.schemas.report import EvidenceReportMetadata, EvidenceReportRequest
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment
from backend.schemas.transaction import TracePath


class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total pages dynamically for 'Page X of Y' footers."""

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
        self.setFillColor(colors.HexColor("#64748B"))

        # Top Running Header
        self.drawString(
            54,
            750,
            "REAL-TIME CRYPTO FRAUD ATTRIBUTION // FORENSIC EVIDENCE DOSSIER",
        )
        self.drawRightString(612 - 54, 750, "CONFIDENTIAL // LAW ENFORCEMENT & COMPLIANCE")

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 742, 612 - 54, 742)

        # Bottom Running Footer
        self.line(54, 45, 612 - 54, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "CRYPTO FRAUD ATTRIBUTION SYSTEM — EVIDENCE REPORT")
        self.drawRightString(
            612 - 54,
            32,
            f"Page {self._pageNumber} of {total_pages}",
        )
        self.restoreState()


class PDFEvidenceReportGenerator:
    """Builds an audit-ready PDF evidence package from case findings."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        primary_color = colors.HexColor("#0F172A")
        slate_color = colors.HexColor("#334155")

        self.styles.add(
            ParagraphStyle(
                "DocTitle",
                parent=self.styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                textColor=primary_color,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "DocSubtitle",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#2563EB"),
                spaceAfter=15,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "SectionHeader",
                parent=self.styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                textColor=primary_color,
                spaceBefore=12,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "MetaLabel",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=slate_color,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "MetaVal",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#0F172A"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                "BodyTextSmall",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=slate_color,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "MonoText",
                parent=self.styles["Normal"],
                fontName="Courier",
                fontSize=7,
                leading=9,
                textColor=colors.HexColor("#1E293B"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                "DisclaimerText",
                parent=self.styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=7.5,
                leading=10,
                textColor=colors.HexColor("#475569"),
            )
        )

    def generate_report(
        self,
        request: EvidenceReportRequest,
        output_dir: Optional[str] = None,
    ) -> tuple[bytes, EvidenceReportMetadata]:
        """Generates the PDF report and returns both the bytes and metadata."""
        report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        filename = f"evidence_report_{request.investigation_id}_{report_id}.pdf"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        story = []

        # 1. Document Title
        story.append(Paragraph("EVIDENCE & ATTRIBUTION REPORT", self.styles["DocTitle"]))
        story.append(
            Paragraph(
                f"CASE ID: {request.investigation_id} // CHAIN: {request.chain.upper()} // REPORT ID: {report_id}",
                self.styles["DocSubtitle"],
            )
        )

        # 1.5 Safe-Handling Advisory Banner
        story.append(self._build_safe_handling_banner())
        story.append(Spacer(1, 10))

        # 2. Case Metadata Table
        story.append(self._build_meta_table(request, report_id))
        story.append(Spacer(1, 12))

        # 3. Executive Assessment Cards (Risk Score & Attribution Confidence)
        story.append(self._build_assessment_cards(request.risk_assessment, request.confidence_assessment))
        story.append(Spacer(1, 14))

        # 4. Explainable Risk Factors Breakdown
        if request.risk_assessment:
            story.append(Paragraph("1. Explainable Risk Factors [FINDINGS]", self.styles["SectionHeader"]))
            story.append(self._build_risk_factors_table(request.risk_assessment))
            story.append(Spacer(1, 12))

        # 5. Attribution Confidence Analysis
        if request.confidence_assessment:
            story.append(Paragraph("2. Attribution Confidence & Reliability Assessment [FINDINGS]", self.styles["SectionHeader"]))
            story.append(self._build_confidence_table(request.confidence_assessment))
            story.append(Spacer(1, 12))

        # 6. Attributed Service Endpoints (Exchange / VASP / Mixer)
        if request.endpoints:
            story.append(Paragraph("3. Identified Service Endpoints & VASPs [FINDINGS]", self.styles["SectionHeader"]))
            story.append(self._build_endpoints_table(request.endpoints))
            story.append(Spacer(1, 12))

        # 7. Multi-Hop Transaction Ledger
        if request.paths:
            story.append(Paragraph("4. Multi-Hop Fund Flow Ledger [FACTS]", self.styles["SectionHeader"]))
            story.append(self._build_transactions_table(request.paths))
            story.append(Spacer(1, 12))

        # 8. Monitoring & Alerts History
        if request.alerts:
            story.append(Paragraph("5. Alerts & Continuous Monitoring Log", self.styles["SectionHeader"]))
            story.append(self._build_alerts_table(request.alerts))
            story.append(Spacer(1, 12))

        # 9. Forensic Limitations & Legal Interpretation Caution (Mandatory)
        story.append(Paragraph("6. Forensic Limitations & Interpretation Caution", self.styles["SectionHeader"]))
        story.append(self._build_legal_disclaimer(request.missing_data_notes))

        # Build document with custom canvas
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Compute tamper-evident cryptographic hash
        import hashlib
        report_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Save to disk if output_dir provided
        storage_path = filename
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            storage_path = os.path.join(output_dir, filename)
            with open(storage_path, "wb") as f:
                f.write(pdf_bytes)

        metadata = EvidenceReportMetadata(
            report_id=report_id,
            investigation_id=request.investigation_id,
            filename=filename,
            file_size_bytes=len(pdf_bytes),
            created_at=datetime.now(timezone.utc).isoformat(),
            storage_path=storage_path,
            download_url=f"/api/investigations/{request.investigation_id}/report/download?format=pdf",
            report_hash=report_hash,
            format="pdf",
        )

        return pdf_bytes, metadata

    def _build_safe_handling_banner(self) -> Table:
        from backend.schemas.report import SAFE_HANDLING_ADVISORY
        content = [
            Paragraph(
                f"<b>SAFE-HANDLING ADVISORY:</b> {SAFE_HANDLING_ADVISORY}",
                self.styles["BodyTextSmall"],
            )
        ]
        t = Table([[content]], colWidths=[504])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#F59E0B")),
                ("TOPPADDING", (0, 0), (0, 0), 5),
                ("BOTTOMPADDING", (0, 0), (0, 0), 5),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ])
        )
        return t

    def _build_meta_table(self, req: EvidenceReportRequest, report_id: str) -> Table:
        data = [
            [
                Paragraph("Target Wallet:", self.styles["MetaLabel"]),
                Paragraph(req.reported_wallet, self.styles["MonoText"]),
                Paragraph("Investigator:", self.styles["MetaLabel"]),
                Paragraph(req.investigator_name, self.styles["MetaVal"]),
            ],
            [
                Paragraph("Blockchain:", self.styles["MetaLabel"]),
                Paragraph(req.chain.capitalize(), self.styles["MetaVal"]),
                Paragraph("Generated Date:", self.styles["MetaLabel"]),
                Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), self.styles["MetaVal"]),
            ],
            [
                Paragraph("Time Window:", self.styles["MetaLabel"]),
                Paragraph(
                    f"{req.time_window_start or 'Inception'} to {req.time_window_end or 'Present'}",
                    self.styles["MetaVal"],
                ),
                Paragraph("Classification:", self.styles["MetaLabel"]),
                Paragraph("OFFICIAL FORENSIC RECORD", self.styles["MetaVal"]),
            ],
        ]
        t = Table(data, colWidths=[80, 200, 90, 134])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        return t

    def _build_assessment_cards(
        self,
        risk: Optional[RiskAssessment],
        conf: Optional[AttributionConfidenceAssessment],
    ) -> Table:
        risk_score_str = f"{risk.overall_score}/100 ({risk.risk_level.value})" if risk else "N/A"
        conf_score_str = (
            f"{int(conf.overall_confidence * 100)}% ({conf.confidence_level.value})" if conf else "N/A"
        )

        risk_color = colors.HexColor("#DC2626") if risk and risk.overall_score >= 50 else colors.HexColor("#16A34A")
        conf_color = colors.HexColor("#2563EB") if conf and conf.overall_confidence >= 0.7 else colors.HexColor("#D97706")

        card_risk = [
            Paragraph("EXPLAINABLE RISK SCORE", self.styles["MetaLabel"]),
            Paragraph(f"<b><font size='14' color='{risk_color.hexval()}'>{risk_score_str}</font></b>", self.styles["Normal"]),
            Paragraph(risk.summary_rationale if risk else "No risk score computed.", self.styles["BodyTextSmall"]),
        ]
        card_conf = [
            Paragraph("ATTRIBUTION CONFIDENCE", self.styles["MetaLabel"]),
            Paragraph(f"<b><font size='14' color='{conf_color.hexval()}'>{conf_score_str}</font></b>", self.styles["Normal"]),
            Paragraph(
                f"Primary Attributed Entity: <b>{conf.primary_entity or 'Unattributed'}</b> ({conf.primary_category or 'N/A'})"
                if conf else "No confidence evaluated.",
                self.styles["BodyTextSmall"],
            ),
        ]

        t = Table([[card_risk, card_conf]], colWidths=[252, 252])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FEF2F2" if risk and risk.overall_score >= 50 else "#F0FDF4")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#EFF6FF")),
                ("BOX", (0, 0), (0, 0), 1, risk_color),
                ("BOX", (1, 0), (1, 0), 1, conf_color),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        return t

    def _build_risk_factors_table(self, risk: RiskAssessment) -> Table:
        headers = [
            Paragraph("<b>Factor Name</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Status</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Pts</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Investigative Rationale & Evidence</b>", self.styles["MetaLabel"]),
        ]
        rows = [headers]

        for f in risk.factors:
            status_text = "<font color='#DC2626'>TRIGGERED</font>" if f.triggered else "<font color='#16A34A'>CLEAN</font>"
            rows.append([
                Paragraph(f.factor_name, self.styles["MetaVal"]),
                Paragraph(status_text, self.styles["MetaVal"]),
                Paragraph(f"+{f.score_contribution:.0f}", self.styles["MetaVal"]),
                Paragraph(f.rationale, self.styles["BodyTextSmall"]),
            ])

        t = Table(rows, colWidths=[120, 65, 35, 284])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        return t

    def _build_confidence_table(self, conf: AttributionConfidenceAssessment) -> Table:
        headers = [
            Paragraph("<b>Confidence Metric</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Score</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Weight</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Attribution Provenance & Attenuation Rationale</b>", self.styles["MetaLabel"]),
        ]
        rows = [headers]

        for f in conf.factors:
            rows.append([
                Paragraph(f.factor_name, self.styles["MetaVal"]),
                Paragraph(f"{f.score_contribution:.2f}", self.styles["MetaVal"]),
                Paragraph(f"{f.weight:.2f}", self.styles["MetaVal"]),
                Paragraph(f.rationale, self.styles["BodyTextSmall"]),
            ])

        t = Table(rows, colWidths=[130, 45, 45, 284])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        return t

    def _build_endpoints_table(self, endpoints: List[EndpointMatchResult]) -> Table:
        headers = [
            Paragraph("<b>Endpoint Address</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Entity Name</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Category</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Hop</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Provenance / Source</b>", self.styles["MetaLabel"]),
        ]
        rows = [headers]

        for ep in endpoints:
            if ep.is_matched and ep.label:
                source_desc = f"{ep.label.source} ({ep.label.verification_status.value})"
                rows.append([
                    Paragraph(ep.address, self.styles["MonoText"]),
                    Paragraph(f"<b>{ep.label.entity_name}</b>", self.styles["MetaVal"]),
                    Paragraph(ep.label.entity_category.value, self.styles["MetaVal"]),
                    Paragraph(str(ep.hop_distance or "—"), self.styles["MetaVal"]),
                    Paragraph(source_desc, self.styles["BodyTextSmall"]),
                ])
            else:
                rows.append([
                    Paragraph(ep.address, self.styles["MonoText"]),
                    Paragraph("<i>Unknown Counterparty</i>", self.styles["MetaVal"]),
                    Paragraph("UNKNOWN", self.styles["MetaVal"]),
                    Paragraph(str(ep.hop_distance or "—"), self.styles["MetaVal"]),
                    Paragraph("Not identified in registry", self.styles["BodyTextSmall"]),
                ])

        t = Table(rows, colWidths=[130, 100, 80, 30, 164])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        return t

    def _build_transactions_table(self, paths: List[TracePath]) -> Table:
        headers = [
            Paragraph("<b>Hop</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Tx Hash</b>", self.styles["MetaLabel"]),
            Paragraph("<b>From</b>", self.styles["MetaLabel"]),
            Paragraph("<b>To</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Amount</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Timestamp (UTC)</b>", self.styles["MetaLabel"]),
        ]
        rows = [headers]

        for p in paths:
            for h in p.hops:
                tx = h.transaction
                rows.append([
                    Paragraph(f"Hop {h.hop_number}", self.styles["MetaVal"]),
                    Paragraph(f"{tx.tx_hash[:10]}...{tx.tx_hash[-6:]}", self.styles["MonoText"]),
                    Paragraph(f"{tx.from_address[:8]}...{tx.from_address[-4:]}", self.styles["MonoText"]),
                    Paragraph(f"{tx.to_address[:8]}...{tx.to_address[-4:]}", self.styles["MonoText"]),
                    Paragraph(f"{tx.amount} {tx.asset_symbol}", self.styles["MetaVal"]),
                    Paragraph(
                        tx.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(tx.timestamp, "strftime") else str(tx.timestamp).replace("T", " ")[:16],
                        self.styles["MetaVal"],
                    ),
                ])

        t = Table(rows, colWidths=[40, 110, 95, 95, 80, 84])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
        )
        return t

    def _build_alerts_table(self, alerts: List[Alert]) -> Table:
        headers = [
            Paragraph("<b>Severity</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Alert Title</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Triggered Details</b>", self.styles["MetaLabel"]),
            Paragraph("<b>Timestamp</b>", self.styles["MetaLabel"]),
        ]
        rows = [headers]

        for a in alerts:
            sev_color = "#DC2626" if a.severity.value in ["HIGH", "CRITICAL"] else "#2563EB"
            rows.append([
                Paragraph(f"<font color='{sev_color}'><b>{a.severity.value}</b></font>", self.styles["MetaVal"]),
                Paragraph(a.title, self.styles["MetaVal"]),
                Paragraph(a.message, self.styles["BodyTextSmall"]),
                Paragraph(a.created_at[:16].replace("T", " "), self.styles["MetaVal"]),
            ])

        t = Table(rows, colWidths=[65, 140, 215, 84])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
        )
        return t

    def _build_legal_disclaimer(self, missing_data_notes: Optional[str]) -> Table:
        disclaimer_paragraphs = [
            Paragraph(
                "<b>MANDATORY FORENSIC INTERPRETATION CAUTION:</b>",
                self.styles["MetaLabel"],
            ),
            Paragraph(
                "A labeled exchange endpoint does not prove who owns the receiving wallet or who controlled the funds. "
                "A transaction path is observed cryptographic evidence; claims about identity, intent, or the continuity "
                "of particular funds require additional off-chain corroboration, legal process, or exchange subpoena records.",
                self.styles["DisclaimerText"],
            ),
            Spacer(1, 4),
            Paragraph(
                "<b>DATA PROVENANCE & UNCERTAINTY:</b> All address labels cite verifiable sources. Unverified community labels "
                "are separated from certified regulatory entries. Multi-hop fund flows are subject to graph attenuation, "
                "co-mingling, and non-custodial aggregators.",
                self.styles["DisclaimerText"],
            ),
        ]
        if missing_data_notes:
            disclaimer_paragraphs.append(Spacer(1, 4))
            disclaimer_paragraphs.append(
                Paragraph(f"<b>DATA GAPS NOTED BY INVESTIGATOR:</b> {missing_data_notes}", self.styles["DisclaimerText"])
            )

        t = Table([[disclaimer_paragraphs]], colWidths=[504])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#94A3B8")),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ])
        )
        return t


global_pdf_generator = PDFEvidenceReportGenerator()
