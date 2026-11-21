import React, { useState, useEffect } from 'react';
import { Trophy, TrendingUp, TrendingDown, Award, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import type { WardScore } from '../types';

function overallScore(w: WardScore): number {
  const m = w.metrics;
  // Weighted: resolution 30%, citizen-verified 25%, no-overdue 25%, no-reopen 20%
  const resolutionPct  = m.resolution_rate;
  const verifiedPct    = m.citizen_verified_rate;
  const onTimePct      = m.total_tickets > 0 ? Math.max(0, 100 - (m.overdue / m.total_tickets) * 100) : 100;
  const noReopenPct    = m.resolution_rate > 0 ? Math.max(0, 100 - m.reopen_rate) : 100;
  return Math.round(resolutionPct * 0.30 + verifiedPct * 0.25 + onTimePct * 0.25 + noReopenPct * 0.20);
}

const scoreColor = (s: number) => s >= 80 ? 'text-green-600' : s >= 60 ? 'text-yellow-600' : 'text-red-600';
const scoreBg    = (s: number) => s >= 80 ? 'bg-green-100' : s >= 60 ? 'bg-yellow-100' : 'bg-red-100';
const badge      = (i: number) => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`;

export default function PublicScoreboard() {
  const [wards, setWards]   = useState<WardScore[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getWardScores();
      // Sort by computed overall score descending
      setWards([...data].sort((a, b) => overallScore(b) - overallScore(a)));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4" />
        <p className="text-gray-600">Loading scoreboard…</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center gap-3">
            <Trophy className="w-10 h-10 text-yellow-500" />
            <h1 className="text-4xl font-bold text-gray-900">Ward Performance</h1>
          </div>
          <p className="text-center text-gray-600 mt-1">Transparent accountability — updated live</p>
          <div className="flex justify-center mt-3">
            <button onClick={load} className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">

        {wards.length === 0 ? (
          <div className="card text-center py-16">
            <Trophy className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-600 mb-2">No ward data yet</h2>
            <p className="text-gray-400 text-sm">
              Ward scores appear once tickets are submitted and assigned to wards.<br />
              Submit a report to get started!
            </p>
          </div>
        ) : (
          <>
            {/* Podium — top 3 */}
            {wards.length >= 3 && (
              <div className="grid grid-cols-3 gap-4 mb-12 max-w-3xl mx-auto">
                {[wards[1], wards[0], wards[2]].map((w, i) => {
                  const podiumIdx = [1, 0, 2][i];
                  const sc = overallScore(w);
                  return (
                    <div key={w.ward_id} className={`card text-center ${podiumIdx === 0 ? 'border-2 border-yellow-400 bg-yellow-50' : ''} ${podiumIdx === 1 ? 'mt-6' : podiumIdx === 2 ? 'mt-6' : ''}`}>
                      <div className="text-4xl mb-1">{badge(podiumIdx)}</div>
                      <h3 className="font-bold">{w.ward_name}</h3>
                      <div className={`text-3xl font-bold my-1 ${scoreColor(sc)}`}>{sc}</div>
                      <p className="text-xs text-gray-500">{w.metrics.total_tickets} tickets</p>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Full table */}
            <div className="max-w-5xl mx-auto space-y-3">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Complete Rankings</h2>
              {wards.map((w, idx) => {
                const sc = overallScore(w);
                const m  = w.metrics;
                return (
                  <div key={w.ward_id} className="card hover:shadow-lg transition-shadow">
                    <div className="flex items-center gap-6 flex-wrap">
                      {/* Rank */}
                      <div className="text-3xl font-bold text-gray-400 w-12 text-center shrink-0">
                        {badge(idx)}
                      </div>

                      {/* Name */}
                      <div className="flex-1 min-w-32">
                        <h3 className="text-lg font-bold">{w.ward_name}</h3>
                        <p className="text-xs text-gray-500">Ward #{w.ward_number}</p>
                      </div>

                      {/* Metrics */}
                      <div className="grid grid-cols-5 gap-4 text-center flex-1">
                        <div>
                          <div className={`text-xl font-bold ${scoreColor(sc)}`}>{sc}</div>
                          <p className="text-xs text-gray-500">Score</p>
                        </div>
                        <div>
                          <div className="text-lg font-semibold">{m.resolution_rate.toFixed(0)}%</div>
                          <p className="text-xs text-gray-500">Resolved</p>
                        </div>
                        <div>
                          <div className="text-lg font-semibold">{m.citizen_verified_rate.toFixed(0)}%</div>
                          <p className="text-xs text-gray-500">Verified</p>
                        </div>
                        <div>
                          <div className="text-lg font-semibold text-red-500">{m.overdue}</div>
                          <p className="text-xs text-gray-500">Overdue</p>
                        </div>
                        <div>
                          <div className="text-lg font-semibold">{m.total_tickets}</div>
                          <p className="text-xs text-gray-500">Tickets</p>
                        </div>
                      </div>

                      {/* Trend */}
                      {sc >= 70
                        ? <TrendingUp className="w-7 h-7 text-green-500 shrink-0" />
                        : <TrendingDown className="w-7 h-7 text-red-500 shrink-0" />}
                    </div>

                    {/* Detail row */}
                    <div className="mt-4 pt-3 border-t border-gray-100 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div><span className="text-gray-500">Avg resolution:</span> <strong>{m.avg_resolution_hours.toFixed(1)}h</strong></div>
                      <div><span className="text-gray-500">Reopened:</span> <strong className="text-orange-600">{m.reopened}</strong></div>
                      <div><span className="text-gray-500">Reopen rate:</span> <strong>{m.reopen_rate.toFixed(1)}%</strong></div>
                      <div><span className="text-gray-500">Total resolved:</span> <strong className="text-green-600">{m.resolved}</strong></div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            <div className="card max-w-3xl mx-auto mt-8 text-sm">
              <h3 className="font-bold mb-3">Scoring Methodology</h3>
              <div className="grid grid-cols-3 gap-3">
                {[[85,'80+ Excellent'],[70,'60–79 Good'],[40,'<60 Needs work']].map(([s,l]) => (
                  <div key={s} className={`px-3 py-2 rounded-lg ${scoreBg(s as number)} ${scoreColor(s as number)} font-semibold text-center`}>{l}</div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Score = Resolution 30% + Citizen-verified 25% + On-time 25% + No-reopen 20%
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
