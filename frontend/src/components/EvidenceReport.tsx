import { useState } from 'react';
import { FileText, Download } from 'lucide-react';
import { apiFetch, apiJson } from '../lib/api';

interface EvidenceReportProps {
  activeCase: string | null;
}

const EvidenceReport: React.FC<EvidenceReportProps> = ({ activeCase }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<any>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  const generateReport = async () => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      const metadata = await apiJson(`/api/investigations/${activeCase}/report`, { method: 'POST' });
      setMeta(metadata);

      // The download route needs the auth header, so fetch the PDF as a blob
      const res = await apiFetch(`/api/investigations/${activeCase}/report/download`);
      if (!res.ok) throw new Error(`${res.status}: could not download the PDF`);
      const blob = await res.blob();
      setPdfUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200 text-center">
        <FileText className="mx-auto h-16 w-16 text-indigo-200 mb-4" />
        <h2 className="text-2xl font-bold mb-2 text-gray-800">Generate Evidence Report</h2>
        <p className="text-gray-600 mb-8 max-w-lg mx-auto">
          Generate an investigator-ready PDF report containing transaction hashes, timestamps, wallet paths, labels, sources, and known limitations.
        </p>

        {error && (
          <div className="mb-6 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">{error}</div>
        )}

        {pdfUrl ? (
          <div className="p-6 bg-green-50 border border-green-200 rounded-lg max-w-md mx-auto">
            <h3 className="text-green-800 font-semibold mb-2">Report Ready</h3>
            {meta && (
              <p className="text-green-900 text-sm mb-3">
                {meta.report_id} · {(meta.file_size_bytes / 1024).toFixed(1)} KB
              </p>
            )}
            <a
              href={pdfUrl}
              download={meta?.filename ?? 'evidence_report.pdf'}
              className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              <Download className="mr-2 h-4 w-4" />
              Download PDF
            </a>
          </div>
        ) : (
          <button
            onClick={generateReport}
            disabled={loading}
            className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:bg-indigo-300 transition-colors"
          >
            {loading ? 'Generating...' : 'Generate Report'}
          </button>
        )}
      </div>
    </div>
  );
};

export default EvidenceReport;
