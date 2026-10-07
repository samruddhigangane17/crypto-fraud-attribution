"""Unit tests for ReportLab PDF Evidence Report Generator (Member 2 Deliverable)."""

import os
import tempfile
import pytest

from backend.mock_data.mock_case import create_mock_investigation_request
from backend.reports.pdf_generator import PDFEvidenceReportGenerator


@pytest.fixture
def pdf_gen():
    return PDFEvidenceReportGenerator()


def test_generate_pdf_in_memory(pdf_gen):
    """Test generating PDF binary data in memory."""
    req = create_mock_investigation_request()
    pdf_bytes, metadata = pdf_gen.generate_report(req)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    # PDF magic number
    assert pdf_bytes.startswith(b"%PDF-")

    assert metadata.investigation_id == req.investigation_id
    assert metadata.filename.startswith("evidence_report_")
    assert metadata.file_size_bytes == len(pdf_bytes)


def test_generate_pdf_to_disk(pdf_gen):
    """Test generating and saving PDF to output directory."""
    req = create_mock_investigation_request()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_bytes, metadata = pdf_gen.generate_report(req, output_dir=tmp_dir)

        assert os.path.exists(metadata.storage_path)
        assert os.path.getsize(metadata.storage_path) == len(pdf_bytes)
        assert metadata.storage_path.endswith(".pdf")
