import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, MapPin, Clock, User, CheckCircle2, XCircle,
  AlertTriangle, FileText, ThumbsUp, ThumbsDown, AlertCircle
} from 'lucide-react';
import { api } from '../services/api';
import type { Ticket, Event } from '../types';
import Button from '../components/shared/Button';

const STATUS_COLORS: Record<string, string> = {
  open:         'bg-amber-100 text-amber-800',
  assigned:     'bg-purple-100 text-purple-800',
  in_progress:  'bg-yellow-100 text-yellow-800',
  needs_review: 'bg-red-100 text-red-800',
  resolved:     'bg-green-100 text-green-800',
  reopened:     'bg-orange-100 text-orange-800',
};

const KIND_ICONS: Record<string, string> = {
  created:               '🆕',
  duplicate_merged:      '🔗',
  repeat_defect_detected:'🔄',
  resolution_submitted:  '📸',
  citizen_verified:      '✅',
  reopened_by_citizen:   '🔓',
  clock_stopped:         '⏸️',
  escalated:             '⬆️',
};

function SlaBar({ deadline, clockStopped }: { deadline: string; clockStopped: boolean }) {
  const now  = new Date();
  const due  = new Date(deadline);
  const diff = due.getTime() - now.getTime();
  const isOverdue = diff < 0;

  return (
    <div className={`p-3 rounded-lg text-sm ${isOverdue ? 'bg-red-50 border border-red-200' : 'bg-blue-50 border border-blue-200'}`}>
      <p className={`font-semibold ${isOverdue ? 'text-red-700' : 'text-blue-700'}`}>
        {isOverdue
          ? `⚠️ Overdue by ${Math.abs(Math.round(diff / 3600000))}h`
          : `⏱ ${Math.round(diff / 3600000)}h remaining`}
      </p>
      <p className="text-xs text-gray-500 mt-0.5">Deadline: {due.toLocaleString()}</p>
      {clockStopped && <p className="text-xs text-orange-600 mt-0.5">⏸️ Clock stopped</p>}
    </div>
  );
}

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  useEffect(() => {
    if (id) load();
  }, [id]);

  const load = async () => {
    try {
      const data = await api.getTicketDetail(id!);
      // Backend returns the ticket fields directly + events array
      setTicket(data as unknown as Ticket);
      setEvents((data as any).events || []);
    } catch {
      /* handled by showing null state */
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (verified: boolean) => {
    setFeedbackLoading(true);
    try {
      await api.submitFeedback(id!, verified);
      await load();
    } catch {
      alert('Failed to submit feedback');
    } finally {
      setFeedbackLoading(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600">Loading ticket…</p>
      </div>
    </div>
  );

  if (!ticket) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="card text-center">
        <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ticket Not Found</h2>
        <Button onClick={() => navigate('/')}>Go Home</Button>
      </div>
    </div>
  );

  const isOverdue = new Date() > new Date(ticket.sla_deadline) && ticket.status !== 'resolved';
  const imgBase  = 'http://localhost:8000';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="container mx-auto px-4 py-6">
          <Button onClick={() => navigate(-1)} variant="secondary" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Ticket #{ticket.id}</h1>
              <p className="text-gray-500 text-sm">{new Date(ticket.created_at).toLocaleString()}</p>
            </div>
            <div className={`px-4 py-2 rounded-full font-semibold capitalize ${STATUS_COLORS[ticket.status] || 'bg-gray-100 text-gray-800'}`}>
              {ticket.status.replace('_', ' ')}
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-3 gap-8">

          {/* ── LEFT: main content ── */}
          <div className="lg:col-span-2 space-y-6">

            {/* Images */}
            <div className="card">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Issue Details</h2>

              <div className="grid sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-sm font-semibold text-gray-600 mb-1">📷 Before (problem)</p>
                  <img
                    src={`${imgBase}/${ticket.before_image}`}
                    alt="Before"
                    className="w-full rounded-lg object-cover h-48"
                    onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/400x300?text=No+Image'; }}
                  />
                </div>
                {ticket.after_image && (
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">✅ After (repair)</p>
                    <img
                      src={`${imgBase}/${ticket.after_image}`}
                      alt="After"
                      className="w-full rounded-lg object-cover h-48 border-2 border-green-400"
                    />
                    {ticket.verification_score !== undefined && (
                      <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-blue-800">
                        AI Verification: <strong>{((ticket.verification_score ?? 0) * 100).toFixed(0)}%</strong>
                        {ticket.verification_details && (
                          <span> · {ticket.verification_details.orb_matches} ORB matches · SSIM {(ticket.verification_details.structural_similarity * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Category & flags */}
              <div className="flex flex-wrap gap-2 text-sm">
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-semibold capitalize">
                  {ticket.category.replace('_', ' ')}
                </span>
                {(ticket.reporter_count > 1) && (
                  <span className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full">
                    👥 {ticket.reporter_count} reports merged
                  </span>
                )}
                {ticket.is_repeat_defect && (
                  <span className="px-3 py-1 bg-red-100 text-red-800 rounded-full">🔄 Repeat Defect</span>
                )}
                {ticket.escalation_level > 0 && (
                  <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full">
                    ⬆️ Escalated (level {ticket.escalation_level})
                  </span>
                )}
                {isOverdue && (
                  <span className="px-3 py-1 bg-red-600 text-white rounded-full">⏰ OVERDUE</span>
                )}
              </div>
            </div>

            {/* Priority reasons */}
            {ticket.priority_reasons?.length > 0 && (
              <div className="card">
                <h2 className="text-xl font-bold text-gray-900 mb-3">🎯 Why this priority?</h2>
                <p className="text-2xl font-bold text-blue-700 mb-3">Score: {ticket.priority?.toFixed(1)}</p>
                <ul className="space-y-1">
                  {ticket.priority_reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-500 mt-0.5">•</span> {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Citizen feedback prompt */}
            {ticket.status === 'resolved' && ticket.citizen_verified === undefined && (
              <div className="card bg-yellow-50 border-2 border-yellow-300">
                <h3 className="font-bold text-lg text-gray-900 mb-2">Was the issue actually fixed?</h3>
                <p className="text-gray-600 text-sm mb-4">
                  Please confirm so we can hold contractors accountable.
                </p>
                <div className="flex gap-3">
                  <Button onClick={() => handleFeedback(true)} loading={feedbackLoading} className="flex-1">
                    <ThumbsUp className="w-4 h-4 mr-2" /> Yes, it's fixed
                  </Button>
                  <Button onClick={() => handleFeedback(false)} loading={feedbackLoading} variant="secondary" className="flex-1">
                    <ThumbsDown className="w-4 h-4 mr-2" /> No, still broken
                  </Button>
                </div>
              </div>
            )}

            {ticket.citizen_verified !== undefined && (
              <div className={`card ${ticket.citizen_verified ? 'bg-green-50 border-2 border-green-300' : 'bg-red-50 border-2 border-red-300'}`}>
                <div className="flex items-center gap-3">
                  {ticket.citizen_verified
                    ? <><CheckCircle2 className="w-8 h-8 text-green-600" /><div><p className="font-bold text-green-900">Verified by Citizen ✅</p><p className="text-sm text-green-700">Issue confirmed as resolved</p></div></>
                    : <><XCircle className="w-8 h-8 text-red-600" /><div><p className="font-bold text-red-900">Not Verified ❌</p><p className="text-sm text-red-700">{ticket.citizen_feedback || 'Citizen reported as unresolved — ticket reopened'}</p></div></>
                  }
                </div>
              </div>
            )}

            {/* Timeline */}
            <div className="card">
              <h2 className="text-xl font-bold text-gray-900 mb-4">📋 Timeline</h2>
              {events.length === 0
                ? <p className="text-gray-500 text-sm">No events yet.</p>
                : (
                  <ol className="relative border-l border-gray-300 ml-2 space-y-4">
                    {events.map((ev) => (
                      <li key={ev.id} className="ml-4">
                        <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-blue-500 border-2 border-white" />
                        <p className="font-semibold text-gray-900 capitalize">
                          {KIND_ICONS[ev.kind] || '📌'} {ev.kind.replace(/_/g, ' ')}
                        </p>
                        {ev.detail && <p className="text-sm text-gray-600">{ev.detail}</p>}
                        <p className="text-xs text-gray-400">{new Date(ev.at).toLocaleString()}</p>
                      </li>
                    ))}
                  </ol>
                )}
            </div>
          </div>

          {/* ── RIGHT: sidebar ── */}
          <div className="space-y-6">

            {/* Location */}
            <div className="card">
              <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                <MapPin className="w-5 h-5" /> Location
              </h3>
              <p className="font-mono text-sm text-gray-600">
                {ticket.lat.toFixed(5)}, {ticket.lng.toFixed(5)}
              </p>
              <a
                href={`https://maps.google.com/?q=${ticket.lat},${ticket.lng}`}
                target="_blank" rel="noreferrer"
                className="text-xs text-blue-600 hover:underline mt-1 inline-block"
              >
                Open in Google Maps ↗
              </a>
            </div>

            {/* SLA */}
            <div className="card">
              <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                <Clock className="w-5 h-5" /> SLA Timer
              </h3>
              <SlaBar deadline={ticket.sla_deadline} clockStopped={ticket.clock_stopped} />
              {ticket.clock_stop_reason && (
                <p className="text-xs text-gray-500 mt-2">Reason: {ticket.clock_stop_reason}</p>
              )}
            </div>

            {/* Assignment */}
            <div className="card">
              <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                <User className="w-5 h-5" /> Assignment
              </h3>
              <div className="text-sm space-y-1">
                <div><span className="text-gray-500">Severity:</span> <span className="font-semibold">{ticket.severity}/10</span></div>
                {ticket.ward_id && <div><span className="text-gray-500">Ward:</span> <span className="font-semibold">#{ticket.ward_id}</span></div>}
                {ticket.assigned_officer_id && <div><span className="text-gray-500">Officer:</span> <span className="font-semibold">#{ticket.assigned_officer_id}</span></div>}
              </div>
            </div>

            {/* Evidence report */}
            {ticket.is_repeat_defect && (
              <div className="card">
                <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <FileText className="w-5 h-5" /> Contractor Evidence
                </h3>
                <p className="text-xs text-gray-600 mb-3">
                  This spot was repaired before. Download the evidence report to hold the contractor accountable.
                </p>
                <Button
                  onClick={() => api.downloadEvidence(id!)}
                  variant="secondary"
                  className="w-full"
                >
                  📄 Download Evidence PDF
                </Button>
              </div>
            )}

            {/* Verification details */}
            {ticket.verification_details && (
              <div className="card">
                <h3 className="font-bold text-gray-900 mb-3">🔬 Verification Checks</h3>
                <ul className="text-sm space-y-1">
                  <li>{ticket.verification_details.location_ok ? '✅' : '❌'} Location match ({ticket.verification_details.distance_m}m away)</li>
                  <li>{ticket.verification_details.scene_match_ok ? '✅' : '❌'} Scene match ({ticket.verification_details.orb_matches} ORB features)</li>
                  <li>{ticket.verification_details.defect_check_ok ? '✅' : '❌'} Defect gone</li>
                </ul>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
