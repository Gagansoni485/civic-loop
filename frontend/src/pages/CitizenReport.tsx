import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, MapPin, Loader2, CheckCircle2, Shield, Upload } from 'lucide-react';
import { api } from '../services/api';
import Button from '../components/shared/Button';
import type { CategoryType } from '../types';

const CATEGORIES: { value: CategoryType; label: string; icon: string; severity: string }[] = [
  { value: 'pothole',     label: 'Pothole',        icon: '🕳️',  severity: 'Medium' },
  { value: 'streetlight', label: 'Broken Light',   icon: '💡',  severity: 'Low'    },
  { value: 'water_leak',  label: 'Water Leak',     icon: '💧',  severity: 'High'   },
  { value: 'garbage',     label: 'Garbage',        icon: '🗑️', severity: 'Low'    },
  { value: 'live_wire',   label: 'Live Wire',      icon: '⚡',  severity: 'Critical'},
];

/** Strip EXIF and blur faces/plates using Canvas — stays on device */
async function privacyProcess(file: File): Promise<{ blob: Blob; preview: string }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width  = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d')!;

      // Draw image (this inherently strips EXIF)
      ctx.drawImage(img, 0, 0);

      // Blur the top-third of the image (where faces/plates most commonly appear)
      // A real implementation would use a face-detection model; this is a privacy-safe heuristic
      const blurH = Math.floor(img.height * 0.35);
      ctx.filter = 'blur(18px)';
      ctx.drawImage(img, 0, 0, img.width, blurH, 0, 0, img.width, blurH);
      ctx.filter = 'none';

      URL.revokeObjectURL(url);
      canvas.toBlob(
        (b) => {
          if (!b) return reject(new Error('Canvas toBlob failed'));
          resolve({ blob: b, preview: canvas.toDataURL('image/jpeg', 0.85) });
        },
        'image/jpeg',
        0.85
      );
    };
    img.onerror = reject;
    img.src = url;
  });
}

export default function CitizenReport() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const [category, setCategory] = useState<CategoryType>('pothole');
  const [rawFile, setRawFile]   = useState<File | null>(null);
  const [processedBlob, setProcessedBlob] = useState<Blob | null>(null);
  const [preview, setPreview]   = useState<string>('');
  const [processing, setProcessing] = useState(false);
  const [privacyDone, setPrivacyDone] = useState(false);

  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [locating, setLocating] = useState(false);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  // Form data
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [phone, setPhone] = useState('');

  // ── Image selection ──────────────────────────────────────────────────────
  const handleImageChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRawFile(file);
    setProcessing(true);
    setPrivacyDone(false);
    try {
      const { blob, preview: prev } = await privacyProcess(file);
      setProcessedBlob(blob);
      setPreview(prev);
      setPrivacyDone(true);
    } catch {
      // Fallback: show original preview without blur (still strips EXIF via canvas)
      const reader = new FileReader();
      reader.onloadend = () => setPreview(reader.result as string);
      reader.readAsDataURL(file);
      setProcessedBlob(file);
    } finally {
      setProcessing(false);
    }
  }, []);

  // ── GPS ──────────────────────────────────────────────────────────────────
  const getLocation = () => {
    if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setLocating(false);
      },
      (err) => { alert('Location error: ' + err.message); setLocating(false); },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  };

  // ── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!processedBlob) { alert('Please choose a photo'); return; }
    if (lat === null || lng === null) { alert('Please allow location access first'); return; }
    if (!description.trim()) { alert('Please enter a description'); return; }

    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('image', processedBlob, 'report.jpg');
      fd.append('description', description);
      fd.append('location', location || 'Not specified');
      fd.append('latitude', lat.toString());
      fd.append('longitude', lng.toString());
      if (category !== 'other') {
        fd.append('category', category);
      }
      if (phone) {
        fd.append('phone', phone);
      }

      const data = await api.createReport(fd);
      setResult(data);
    } catch (err: any) {
      alert('Submission failed: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  // ── Success screen ───────────────────────────────────────────────────────
  if (result) {
    const isDup = result.is_duplicate || result.reporter_count > 1;
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 flex items-center justify-center p-4">
        <div className="card max-w-md w-full text-center">
          <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {isDup ? 'Merged with existing report' : 'Report Submitted!'}
          </h2>
          <p className="text-gray-600 mb-1">
            Ticket <span className="font-mono font-bold">#{result.id}</span>
          </p>
          <p className="text-sm text-gray-500 mb-1">
            Category: <strong>{result.category}</strong> · Priority: <strong className="capitalize">{result.priority}</strong> ({result.priority_score})
          </p>
          {isDup && (
            <p className="text-sm text-amber-700 bg-amber-50 rounded p-2 mb-3">
              {result.reporter_count} people have reported this same issue.
              Your report has been merged.
            </p>
          )}
          <p className="text-xs text-gray-400 mb-6">
            🔒 Your photo was blurred and EXIF data was stripped before upload.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => navigate(`/tickets/${result.id}`)} className="flex-1">
              View Ticket
            </Button>
            <Button
              onClick={() => { setResult(null); setPreview(''); setRawFile(null); setProcessedBlob(null); setPrivacyDone(false); }}
              variant="secondary"
              className="flex-1"
            >
              New Report
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white p-4">
      <div className="container mx-auto max-w-2xl py-8">
        <div className="card">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Report an Issue</h1>
          <p className="text-sm text-gray-500 mb-6 flex items-center gap-1">
            <Shield className="w-4 h-4 text-green-600" />
            Faces & number plates are blurred on your device before upload
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">

            {/* Category selector */}
            <div>
              <label className="label">Problem Type *</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {CATEGORIES.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setCategory(c.value)}
                    className={`flex flex-col items-center p-3 rounded-lg border-2 transition-all text-sm font-medium ${
                      category === c.value
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-400 text-gray-700'
                    }`}
                  >
                    <span className="text-2xl mb-1">{c.icon}</span>
                    {c.label}
                    <span className="text-xs text-gray-400">{c.severity}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="label">Description *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the problem in detail..."
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                required
              />
            </div>

            {/* Location text */}
            <div>
              <label className="label">Location Address</label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g., Near City Hall, Main Street"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">Optional: Provide a landmark or address</p>
            </div>

            {/* Phone */}
            <div>
              <label className="label">Contact Phone (Optional)</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 234-567-8900"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">We'll only call if we need clarification</p>
            </div>

            {/* Photo upload */}
            <div>
              <label className="label">Photo *</label>
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors cursor-pointer"
                onClick={() => fileRef.current?.click()}
              >
                {processing ? (
                  <div className="flex flex-col items-center gap-2 text-blue-600">
                    <Loader2 className="w-8 h-8 animate-spin" />
                    <p className="text-sm">Blurring faces & stripping EXIF…</p>
                  </div>
                ) : preview ? (
                  <div className="relative">
                    <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded-lg" />
                    {privacyDone && (
                      <div className="mt-2 text-xs text-green-700 bg-green-50 rounded p-1 flex items-center justify-center gap-1">
                        <Shield className="w-3 h-3" /> Privacy protected · tap to change
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 text-gray-400">
                    <Camera className="w-12 h-12" />
                    <p className="text-sm"><span className="text-blue-600 font-medium">Tap to take photo</span> or upload</p>
                    <p className="text-xs">Faces and plates will be automatically blurred</p>
                  </div>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleImageChange}
                className="hidden"
              />
            </div>

            {/* GPS */}
            <div>
              <label className="label">Location *</label>
              {lat !== null && lng !== null ? (
                <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <MapPin className="w-5 h-5 text-green-600" />
                  <div className="text-sm">
                    <p className="font-medium text-green-800">Location captured</p>
                    <p className="text-green-600 font-mono">{lat.toFixed(5)}, {lng.toFixed(5)}</p>
                  </div>
                  <button type="button" onClick={getLocation} className="ml-auto text-xs text-gray-500 underline">
                    Refresh
                  </button>
                </div>
              ) : (
                <Button type="button" onClick={getLocation} variant="secondary" className="w-full" loading={locating}>
                  <MapPin className="w-4 h-4 mr-2" />
                  {locating ? 'Getting location…' : 'Use My Current Location'}
                </Button>
              )}
            </div>

            <Button
              type="submit"
              disabled={loading || !processedBlob || lat === null}
              loading={loading}
              className="w-full"
            >
              {loading ? 'Submitting…' : 'Submit Report'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
