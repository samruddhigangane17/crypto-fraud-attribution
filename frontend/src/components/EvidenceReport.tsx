import { useState } from 'react';
import { FileText, Download, Code, ShieldAlert, CheckCircle } from 'lucide-react';
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

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Safe-Handling Advisory Banner */}
      <div className="p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-md flex items-start space-x-3 text-amber-900 shadow-sm">
        <ShieldAlert className="h-6 w-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-semibold text-sm tracking-wide uppercase">Official Safe-Handling Advisory</h4>
          <p className="text-xs mt-1 text-amber-800">
            Law enforcement officials, regulatory bodies, and genuine recovery processes never ask a victim for private keys,
            seed phrases, OTPs, or upfront recovery fees. Anyone asking for fees or private credentials claiming to be a
            "recovery agent" is engaging in criminal fraud.
          </p>
        </div>
      </div>

      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200 text-center">
        <FileText className="mx-auto h-16 w-16 text-indigo-300 mb-4" />
        <h2 className="text-2xl font-bold mb-2 text-gray-800">Standardized Evidence Dossier</h2>
        <p className="text-gray-600 mb-6 max-w-xl mx-auto text-sm">
          Generate an audit-ready, tamper-evident evidence package in PDF (for court/VASP submission) or canonical JSON
          (for NCRP/SAHYOG system-to-system exchange). Includes cryptographic SHA-256 hash.
        </p>

        {error && (
          <div className="mb-6 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">{error}</div>
        )}

        {pdfUrl || jsonUrl ? (
          <div className="space-y-4 max-w-lg mx-auto">
            <div className="p-5 bg-green-50 border border-green-200 rounded-lg text-left">
              <div className="flex items-center text-green-800 font-semibold mb-2">
                <CheckCircle className="mr-2 h-5 w-5 text-green-600" />
                Evidence Dossier Generated Successfully
              </div>

              {metaPdf && (
                <div className="text-xs text-gray-600 space-y-1 mb-4 bg-white p-3 rounded border border-green-100 font-mono">
                  <div><strong>PDF Report ID:</strong> {metaPdf.report_id}</div>
                  <div className="truncate"><strong>SHA-256 Hash:</strong> {metaPdf.report_hash || 'Computed'}</div>
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3">
                {pdfUrl && (
                  <a
                    href={pdfUrl}
                    download={metaPdf?.filename ?? 'evidence_report.pdf'}
                    className="flex-1 inline-flex items-center justify-center px-4 py-2.5 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium shadow-sm"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download PDF Dossier
                  </a>
                )}
                {jsonUrl && (
                  <a
                    href={jsonUrl}
                    download={metaJson?.filename ?? 'evidence_report.json'}
                    className="flex-1 inline-flex items-center justify-center px-4 py-2.5 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors text-sm font-medium shadow-sm"
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
            className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors shadow-sm"
          >
            {loading ? 'Compiling Evidence Dossier...' : 'Generate Evidence Dossier (PDF & JSON)'}
          </button>
        )}
      </div>
    </div>
  );
};

export default EvidenceReport;
