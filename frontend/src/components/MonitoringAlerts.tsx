import { useEffect, useState } from 'react';
import { Bell, ShieldAlert, CheckCircle } from 'lucide-react';

interface MonitoringAlertsProps {
  activeCase: string | null;
}

const MonitoringAlerts: React.FC<MonitoringAlertsProps> = ({ activeCase }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeCase) return;
    setLoading(true);
    fetch(`http://localhost:8000/api/investigations/${activeCase}/alerts`)
      .then(res => res.json())
      .then(data => setAlerts(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeCase]);

  if (!activeCase) return <div className="p-8 text-center text-gray-500">No active case selected.</div>;
  if (loading) return <div>Loading alerts...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex justify-between items-center mb-6 border-b pb-4">
          <h2 className="text-2xl font-bold text-gray-800 flex items-center">
            <Bell className="mr-3 text-indigo-600" />
            Monitoring and Alerts
          </h2>
          <span className="px-3 py-1 bg-green-100 text-green-800 text-sm font-medium rounded-full flex items-center">
            <CheckCircle className="w-4 h-4 mr-1" />
            Active Monitoring
          </span>
        </div>

        <div className="space-y-4">
          {alerts.length === 0 ? (
            <div className="text-gray-500 text-center py-8">No alerts generated yet.</div>
          ) : (
            alerts.map((alert: any) => (
              <div key={alert.id} className="flex p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                <ShieldAlert className="text-yellow-600 mr-4 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-yellow-900">{alert.event_key.replace('_', ' ').toUpperCase()}</h4>
                  <p className="text-yellow-800 text-sm mt-1">{alert.message}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default MonitoringAlerts;
