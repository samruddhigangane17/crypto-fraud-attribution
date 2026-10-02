import { useState } from 'react';
import { FileText, Download } from 'lucide-react';

interface EvidenceReportProps {
  activeCase: string | null;
}

const EvidenceReport: React.FC<EvidenceReportProps> = ({ activeCase }) => {
  const [loading, setLoading] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const generateReport = async () => {
    if (!activeCase) return;
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/investigations/${activeCase}/report`, {
        method: 'POST'
      });
      await res.json();
      
      const getRes = await fetch(`http://localhost:8000/api/investigations/${activeCase}/report`);
      const getData = await getRes.json();
      setReportUrl(getData.url);
    } catch (err) {
      console.error(err);
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

        {reportUrl ? (
          <div className="p-6 bg-green-50 border border-green-200 rounded-lg max-w-md mx-auto">
            <h3 className="text-green-800 font-semibold mb-2">Report Ready</h3>
            <a 
              href={reportUrl} 
              target="_blank" 
              rel="noreferrer"
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
