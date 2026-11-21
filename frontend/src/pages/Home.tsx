import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquare, BarChart3, Users, Shield, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import type { SystemStats } from '../types';

export default function Home() {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50">

      {/* Hero */}
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">CivicLoop</h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            AI-powered civic complaint management with <strong>verified</strong> repair tracking
            and contractor accountability.
          </p>
        </div>

        {/* Live stats bar */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 max-w-3xl mx-auto">
            {[
              { label: 'Total Reports',  value: stats.total_tickets,   icon: MessageSquare, color: 'text-blue-600' },
              { label: 'Resolved',       value: stats.resolved,         icon: CheckCircle2,  color: 'text-green-600' },
              { label: 'Needs Review',   value: stats.needs_review,     icon: AlertTriangle, color: 'text-amber-600' },
              { label: 'Overdue',        value: stats.overdue,          icon: Clock,         color: 'text-red-600' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="card text-center">
                <Icon className={`w-8 h-8 mx-auto mb-1 ${color}`} />
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-gray-500">{label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Feature cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          <Link to="/report" className="card hover:shadow-xl transition-shadow group">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-200 transition-colors">
                <MessageSquare className="w-8 h-8 text-blue-600" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">Report Issue</h2>
              <p className="text-gray-600 text-sm">
                Photo + GPS. Faces and plates blurred on-device.
                AI classifies and merges duplicate reports automatically.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs text-green-600 font-medium">
                <Shield className="w-3 h-3" /> Privacy protected
              </div>
            </div>
          </Link>

          <Link to="/officer" className="card hover:shadow-xl transition-shadow group">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-green-200 transition-colors">
                <Users className="w-8 h-8 text-green-600" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">Officer Dashboard</h2>
              <p className="text-gray-600 text-sm">
                Priority-sorted job list. Submit repair photos.
                Tickets close only after photo verification passes.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs text-blue-600 font-medium">
                <CheckCircle2 className="w-3 h-3" /> Verified closures only
              </div>
            </div>
          </Link>

          <Link to="/scoreboard" className="card hover:shadow-xl transition-shadow group">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-purple-200 transition-colors">
                <BarChart3 className="w-8 h-8 text-purple-600" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">Public Scoreboard</h2>
              <p className="text-gray-600 text-sm">
                Every ward's performance is public. Resolution rate,
                citizen-verified fixes, and overdue counts — visible to all.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs text-purple-600 font-medium">
                <BarChart3 className="w-3 h-3" /> Full transparency
              </div>
            </div>
          </Link>
        </div>

        {/* How it works */}
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-4xl mx-auto">
          <h3 className="text-2xl font-bold text-center mb-8">How CivicLoop Works</h3>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { n: 1, title: 'Citizen Reports',    desc: 'Photo + GPS. Privacy blur runs on your phone.',   icon: '📱' },
              { n: 2, title: 'AI Classifies',      desc: 'Category, severity & duplicates detected instantly.', icon: '🤖' },
              { n: 3, title: 'SLA Timer Starts',   desc: 'Deadline set. Auto-escalates to commissioner if missed.', icon: '⏱️' },
              { n: 4, title: 'Proof Required',     desc: 'Officer must photo the fix at the same GPS spot.', icon: '✅' },
            ].map(({ n, title, desc, icon }) => (
              <div key={n} className="text-center">
                <div className="w-14 h-14 bg-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-3 text-xl font-bold shadow">
                  {icon}
                </div>
                <h4 className="font-semibold mb-1">{title}</h4>
                <p className="text-sm text-gray-600">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
