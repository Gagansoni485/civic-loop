import React, { useState } from 'react';
import type { Ticket } from '../../types';
import Button from '../shared/Button';
import { ticketAPI } from '../../services/api';

interface TicketCardProps {
  ticket: Ticket;
  onUpdate: () => void;
}

const TicketCard: React.FC<TicketCardProps> = ({ ticket, onUpdate }) => {
  const [showResolutionModal, setShowResolutionModal] = useState(false);
  const [resolutionFile, setResolutionFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);

  const isOverdue = new Date(ticket.sla_deadline) < new Date() && ticket.status !== 'resolved';

  const handleSubmitResolution = async () => {
    if (!resolutionFile) return;

    setSubmitting(true);
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 15000
        });
      });

      const formData = new FormData();
      formData.append('image', resolutionFile);
      formData.append('lat', position.coords.latitude.toString());
      formData.append('lng', position.coords.longitude.toString());
      formData.append('accuracy_m', (position.coords.accuracy || 10).toString());
      formData.append('officer_id', '1');

      const response = await ticketAPI.submitResolution(ticket.id, formData);
      setResult(response);
      
      setTimeout(() => {
        onUpdate();
        setShowResolutionModal(false);
      }, 3000);
    } catch (error) {
      console.error('Failed to submit resolution:', error);
      alert('Failed to submit resolution');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="card hover:shadow-lg transition-shadow">
        <div className="flex gap-4">
          <img
            src={`/${ticket.before_image}`}
            alt={ticket.category}
            className="w-32 h-32 object-cover rounded-lg"
          />
          
          <div className="flex-1">
            <div className="flex justify-between items-start mb-2">
              <div>
                <span className="text-lg font-bold">#{ticket.id}</span>
                <span className={`badge ml-2 ${ticket.status.replace('_', '')}`}>
                  {ticket.status.replace('_', ' ')}
                </span>
                {isOverdue && (
                  <span className="badge ml-2 bg-red-100 text-red-800">⏰ OVERDUE</span>
                )}
              </div>
              <div className="text-sm text-gray-500">
                {new Date(ticket.created_at).toLocaleDateString()}
              </div>
            </div>

            <div className="mb-2">
              <span className="font-semibold text-lg">
                {ticket.category.replace('_', ' ').toUpperCase()}
              </span>
            </div>

            <div className="text-sm text-gray-600 mb-2">
              Priority: <span className="font-semibold">{ticket.priority.toFixed(1)}</span> | 
              {ticket.reporter_count} reporter(s)
              {ticket.is_repeat_defect && ' | 🔄 REPEAT DEFECT'}
            </div>

            <ul className="text-sm text-gray-600 mb-3 space-y-1">
              {ticket.priority_reasons.map((reason, i) => (
                <li key={i}>• {reason}</li>
              ))}
            </ul>

            <div className="text-xs text-gray-500 mb-3">
              📍 {ticket.lat.toFixed(4)}, {ticket.lng.toFixed(4)} | 
              ⏱ Deadline: {new Date(ticket.sla_deadline).toLocaleString()}
            </div>

            {ticket.status !== 'resolved' && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => setShowResolutionModal(true)}
                >
                  📸 Submit Resolution
                </Button>
                {ticket.is_repeat_defect && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      const blob = await ticketAPI.downloadEvidence(ticket.id);
                      const url = URL.createObjectURL(blob);
                      window.open(url);
                    }}
                  >
                    📄 Evidence
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Resolution Modal */}
      {showResolutionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold mb-4">Submit Resolution</h2>
            
            <div className="mb-4">
              <label className="label">Repair Photo</label>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => setResolutionFile(e.target.files?.[0] || null)}
                className="input"
              />
              <p className="text-sm text-gray-500 mt-1">
                Take a photo at the repair location
              </p>
            </div>

            {result && (
              <div className={`p-4 rounded-lg mb-4 ${result.status === 'resolved' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                <h3 className="font-bold mb-2">
                  {result.status === 'resolved' ? '✅ Verification Passed' : '⚠️ Needs Review'}
                </h3>
                {result.verification_details && (
                  <div className="text-sm space-y-1">
                    <div>Score: {(result.verification_details.verification_score * 100).toFixed(0)}%</div>
                    <div>Location: {result.verification_details.location_ok ? '✅' : '❌'} ({result.verification_details.distance_m}m)</div>
                    <div>Scene: {result.verification_details.scene_match_ok ? '✅' : '❌'}</div>
                    <div>Defect Gone: {result.verification_details.defect_check_ok ? '✅' : '❌'}</div>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => setShowResolutionModal(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSubmitResolution}
                loading={submitting}
                disabled={!resolutionFile}
                className="flex-1"
              >
                Submit
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default TicketCard;
