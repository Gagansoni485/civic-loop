import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Home from './pages/Home';
import CitizenReport from './pages/CitizenReport';
import OfficerDashboard from './pages/OfficerDashboard';
import PublicScoreboard from './pages/PublicScoreboard';
import TicketDetail from './pages/TicketDetail';
import Login from './pages/Login';
import Register from './pages/Register';

const App: React.FC = () => {
  const user = localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!) : null;

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/';
  };

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-blue-900 text-white shadow-lg">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-4">
              <Link to="/" className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-amber-500 rounded-lg flex items-center justify-center">
                  <span className="text-2xl font-bold">🏛️</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold">CivicLoop</h1>
                  <p className="text-sm text-blue-200">Verified Civic Repair Tracking</p>
                </div>
              </Link>
              
              <nav className="flex items-center space-x-6">
                <Link to="/" className="hover:text-amber-400 transition">
                  Home
                </Link>
                <Link to="/report" className="hover:text-amber-400 transition">
                  Report Problem
                </Link>
                <Link to="/scoreboard" className="hover:text-amber-400 transition">
                  Performance
                </Link>
                {user ? (
                  <>
                    {(user.role === 'officer' || user.role === 'admin') && (
                      <Link to="/officer" className="hover:text-amber-400 transition">
                        Dashboard
                      </Link>
                    )}
                    <div className="flex items-center space-x-3">
                      <span className="text-sm text-blue-200">
                        {user.full_name} ({user.role})
                      </span>
                      <button
                        onClick={handleLogout}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm transition"
                      >
                        Logout
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <Link to="/login" className="hover:text-amber-400 transition">
                      Login
                    </Link>
                    <Link
                      to="/register"
                      className="px-4 py-2 bg-amber-500 hover:bg-amber-600 rounded font-semibold transition"
                    >
                      Register
                    </Link>
                  </>
                )}
              </nav>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/report" element={<CitizenReport />} />
            <Route path="/officer" element={<OfficerDashboard />} />
            <Route path="/scoreboard" element={<PublicScoreboard />} />
            <Route path="/ticket/:id" element={<TicketDetail />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="bg-gray-800 text-white mt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <h3 className="text-lg font-bold mb-4">About CivicLoop</h3>
                <p className="text-gray-300 text-sm">
                  Ensuring accountability in civic complaints. Tickets close only when repairs are verified with photographic evidence.
                </p>
              </div>
              <div>
                <h3 className="text-lg font-bold mb-4">Features</h3>
                <ul className="text-gray-300 text-sm space-y-2">
                  <li>✓ Location verification</li>
                  <li>✓ Scene matching</li>
                  <li>✓ Privacy-first design</li>
                  <li>✓ Public transparency</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-bold mb-4">Contact</h3>
                <p className="text-gray-300 text-sm">
                  For support or inquiries, contact your local municipal office.
                </p>
              </div>
            </div>
            <div className="mt-8 pt-8 border-t border-gray-700 text-center text-gray-400 text-sm">
              © 2024 CivicLoop. Built for better governance.
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
};

export default App;
