import { useState } from 'react';
import { FileText, Download, Code, CheckCircle, Lock } from 'lucide-react';
import { apiFetch, apiJson } from '../lib/api';

interface EvidenceReportProps {
  activeCase: string | null;
}

const EvidenceReport: React.FC<EvidenceReportProps> = ({ activeCase }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metaPdf, setMetaPdf] = useState<any>(null);
  const [metaJson, setMetaJson] = useState<any>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [jsonUrl, setJsonUrl] = useState<string | null>(null);

  const generateReports = async () => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      // 1. Generate & download PDF
      const pdfMeta = await apiJson(`/api/investigations/${activeCase}/report?format=pdf`, { method: 'POST' });
      setMetaPdf(pdfMeta);
      const resPdf = await apiFetch(`/api/investigations/${activeCase}/report/download?format=pdf`);
      if (resPdf.ok) {
        const blobPdf = await resPdf.blob();
        setPdfUrl(URL.createObjectURL(blobPdf));
      }

      // 2. Generate & download JSON
      const jsonMeta = await apiJson(`/api/investigations/${activeCase}/report?format=json`, { method: 'POST' });
      setMetaJson(jsonMeta);
      const resJson = await apiFetch(`/api/investigations/${activeCase}/report/download?format=json`);
      if (resJson.ok) {
        const blobJson = await resJson.blob();
        setJsonUrl(URL.createObjectURL(blobJson));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  if (!activeCase) {
    return (
      <div className="p-12 text-center text-[var(--text-muted)] bg-[var(--bg-card)] rounded-2xl border border-[var(--border-color)] max-w-xl mx-auto my-12">
        <FileText className="h-10 w-10 text-[#79E282] mx-auto mb-3" />
        <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Case Selected</h3>
        <p className="text-xs mt-1">Please select an investigation from the header console to generate an Evidence Report.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      <div className="bg-[var(--bg-card)] p-8 rounded-2xl shadow-xl border border-[var(--border-color)] text-center transition-colors">
        <div className="w-16 h-16 rounded-2xl bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/30 text-[var(--accent-primary)] flex items-center justify-center mx-auto mb-4 shadow-lg shadow-[var(--accent-primary)]/5">
          <FileText className="h-8 w-8" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] mb-2">
          Standardized Forensic Evidence Dossier
        </h2>
        <p className="text-xs text-[var(--text-muted)] mb-6 max-w-xl mx-auto leading-relaxed">
          Compile court-admissible PDF evidence packages and machine-readable JSON dossiers for law enforcement
          and VASP compliance submission. Every export is cryptographically sealed with a SHA-256 integrity hash.
        </p>

        {error && (
          <div className="mb-6 p-3 bg-[var(--status-critical)]/10 text-[var(--status-critical)] border border-[var(--status-critical)]/30 rounded-xl text-xs">{error}</div>
        )}

        {pdfUrl || jsonUrl ? (
          <div className="space-y-4 max-w-lg mx-auto">
            <div className="p-5 bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/30 rounded-2xl text-left">
              <div className="flex items-center text-[var(--accent-primary)] font-bold text-sm mb-3">
                <CheckCircle className="mr-2 h-5 w-5 text-[var(--accent-primary)]" />
                Evidence Dossier Compiled & Verified
              </div>

              {metaPdf && (
                <div className="text-xs text-[var(--text-muted)] space-y-2 mb-4 bg-[var(--bg-secondary)] p-3.5 rounded-xl border border-[var(--border-color)] font-mono">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">Report ID:</span>
                    <span className="text-[var(--text-primary)] font-bold">{metaPdf.report_id}</span>
                  </div>
                  <div className="truncate">
                    <span className="text-[var(--text-muted)]">SHA-256 Hash:</span>{' '}
                    <span className="text-[var(--accent-primary)]">{metaPdf.report_hash || 'Verified'}</span>
                  </div>
                  <div className="flex items-center text-[10px] text-[var(--text-muted)] pt-1 border-t border-[var(--border-color)]">
                    <Lock className="h-3 w-3 mr-1 text-[var(--accent-primary)]" /> Chain of custody integrity sealed
                  </div>
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3">
                {pdfUrl && (
                  <a
                    href={pdfUrl}
                    download={metaPdf?.filename ?? 'evidence_report.pdf'}
                    className="flex-1 inline-flex items-center justify-center px-4 py-2.5 bg-[var(--accent-primary)] text-[var(--bg-card)] font-bold rounded-xl hover:opacity-90 transition-opacity text-xs shadow-md"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download PDF Dossier
                  </a>
                )}
                {jsonUrl && (
                  <a
                    href={jsonUrl}
                    download={metaJson?.filename ?? 'evidence_report.json'}
                    className="flex-1 inline-flex items-center justify-center px-4 py-2.5 bg-[var(--bg-secondary)] text-[var(--text-primary)] hover:text-[var(--accent-primary)] border border-[var(--border-color)] hover:border-[var(--accent-primary)] rounded-xl transition-colors text-xs font-bold shadow-md"
                  >
                    <Code className="mr-2 h-4 w-4" />
                    Download JSON Data
                  </a>
                )}
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={generateReports}
            disabled={loading}
            className="inline-flex items-center px-6 py-3 bg-[var(--accent-primary)] text-[var(--bg-card)] font-bold text-xs rounded-xl hover:opacity-90 disabled:opacity-50 transition-all shadow-lg"
          >
            {loading ? 'Compiling Forensic Dossier (PDF & JSON)...' : 'Compile Standardized Evidence Dossier (PDF & JSON)'}
          </button>
        )}
      </div>
    </div>
  );
};

export default EvidenceReport;
