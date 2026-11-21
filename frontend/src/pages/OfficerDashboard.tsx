import React, { useState, useEffect } from 'react';
import { Filter, Search, TrendingUp, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import type { Ticket, SystemStats } from '../types';
import TicketCard from '../components/officer/TicketCard';
import Button from '../components/shared/Button';

const CATEGORIES = ['pothole', 'streetlight', 'water_leak', 'garbage', 'live_wire'];
const STATUSES   = ['open', 'assigned', 'in_progress', 'needs_review', 'resolved', 'reopened'];

export default function OfficerDashboard() {
  const [tickets, setTickets]   = useState<Ticket[]>([]);
  const [loading, setLoading]   = useState(true);
  const [stats, setStats]       = useState<SystemStats | null>(null);
  const [searchTerm, setSearch] = useState('');
  const [filters, setFilters]   = useState({
    status: '',
    category: '',
    escalated_only: false,
  });

  useEffect(() => {
    loadTickets();
    loadStats();
  }, [filters]);

  const loadTickets = async () => {
    setLoading(true);
    try {
      const data = await api.getTickets({
        status:         filters.status   || undefined,
        category:       filters.category || undefined,
        escalated_only: filters.escalated_only || undefined,
      });
      setTickets(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (err) {
      console.error(err);
    }
  };

  const filtered = tickets.filter((t) => {
    const q = searchTerm.toLowerCase();
    return (
      !q ||
      t.id.toString().includes(q) ||
      t.category.toLowerCase().includes(q)
    );
  });

  const pending = tickets.filter(t => !['resolved'].includes(t.status)).length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Officer Dashboard</h1>
          <p className="text-gray-600">Manage and resolve civic complaints</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total</p>
                <p className="text-3xl font-bold">{stats?.total_tickets ?? '—'}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-400" />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Pending</p>
                <p className="text-3xl font-bold text-orange-500">{pending}</p>
              </div>
              <Clock className="w-8 h-8 text-orange-400" />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Resolved</p>
                <p className="text-3xl font-bold text-green-500">{stats?.resolved ?? '—'}</p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            </div>
          </div>
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Overdue</p>
                <p className="text-3xl font-bold text-red-500">{stats?.overdue ?? '—'}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="card mb-6">
          <div className="flex flex-wrap gap-4 items-end">
            {/* Search */}
            <div className="flex-1 min-w-48">
              <label className="label">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Ticket ID or category…"
                  className="input pl-10"
                />
              </div>
            </div>

            {/* Status */}
            <div>
              <label className="label">Status</label>
              <select value={filters.status} onChange={e => setFilters({...filters, status: e.target.value})} className="input">
                <option value="">All</option>
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>

            {/* Category */}
            <div>
              <label className="label">Category</label>
              <select value={filters.category} onChange={e => setFilters({...filters, category: e.target.value})} className="input">
                <option value="">All</option>
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select>
            </div>

            {/* Escalated */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.escalated_only}
                onChange={e => setFilters({...filters, escalated_only: e.target.checked})}
                className="w-4 h-4 text-blue-600"
              />
              <span className="text-sm font-medium text-gray-700">Escalated only</span>
            </label>

            <Button onClick={() => { setFilters({ status: '', category: '', escalated_only: false }); setSearch(''); }} variant="secondary">
              <Filter className="w-4 h-4 mr-1" /> Clear
            </Button>
          </div>
        </div>

        {/* Ticket list */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
            <p className="text-gray-600 mt-4">Loading tickets…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-gray-500">No tickets match your filters.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map(ticket => (
              <TicketCard key={ticket.id} ticket={ticket} onUpdate={() => { loadTickets(); loadStats(); }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
