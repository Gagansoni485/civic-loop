# CivicLoop - AI-Powered Civic Complaint Management System

Complete civic complaint management system with AI-powered defect classification, privacy protection, duplicate detection, and accountability tracking.

## 🌟 Features

### Core Features
- **AI Classification**: YOLO-based automatic defect detection and categorization
- **Privacy Protection**: Client-side face/license plate blurring before upload
- **Duplicate Detection**: Automatically merges reports within 50m radius
- **Smart Routing**: Auto-assigns tickets to ward officers
- **SLA Tracking**: Automatic deadline calculation and escalation
- **Priority Scoring**: AI-driven priority based on severity and location
- **Verification System**: Scene matching for repair verification
- **Audit Trail**: Complete event log for accountability

### Tech Stack
**Backend:**
- FastAPI (Python 3.10+)
- SQLAlchemy ORM
- SQLite database
- YOLO (Ultralytics) for image classification
- JWT authentication

**Frontend:**
- React 18 + TypeScript
- Tailwind CSS
- Vite build tool
- Axios for API calls
- Lucide icons

## 📁 Project Structure

```
civicloop-backend/
├── app/
│   ├── main.py              # FastAPI routes and endpoints
│   ├── config.py            # Configuration (SLA, weights, categories)
│   ├── database.py          # Database engine and session
│   ├── models.py            # SQLAlchemy models (User, Ticket, Event, etc.)
│   └── services/
│       ├── auth.py          # JWT authentication
│       ├── classifier.py    # YOLO defect classification
│       ├── duplicates.py    # Duplicate detection (50m radius)
│       ├── priority.py      # Priority score calculation
│       ├── sla.py          # SLA deadline and escalation
│       ├── verification.py  # Repair verification
│       ├── geo.py          # Geospatial calculations
│       ├── privacy_blur.py  # EXIF stripping
│       └── events.py       # Audit log helpers
├── frontend/
│   └── src/
│       ├── pages/          # React pages (Home, Report, Dashboard, etc.)
│       ├── components/     # Reusable UI components
│       ├── services/       # API client
│       ├── types/          # TypeScript definitions
│       └── styles/         # Global CSS
├── models/
│   └── civic/
│       └── civic.pt        # YOLO model for defect classification
├── data/
│   └── zones.sample.json   # Sample zone data
├── tests/
│   └── test_core.py        # Unit tests
├── requirements.txt         # Python dependencies
└── requirements-ml.txt      # ML dependencies (PyTorch + YOLO)
```

## 🚀 Installation

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Git

### Backend Setup

1. **Clone the repository:**
```bash
git clone https://github.com/Gagansoni485/civic-loop.git
cd civic-loop
```

2. **Create virtual environment:**
```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

3. **Install dependencies:**
```bash
# Core dependencies
pip install -r requirements.txt

# ML dependencies (PyTorch CPU + YOLO)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics
```

4. **Run tests:**
```bash
pytest
```

5. **Start backend server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000
API docs: http://localhost:8000/docs

### Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Start development server:**
```bash
npm run dev
```

Frontend will be available at: http://localhost:3000

## 📖 Usage

### For Citizens

1. **Navigate to** http://localhost:3000
2. **Register/Login** (optional - can report anonymously)
3. **Click "Report Issue"**
4. Select problem type (pothole, streetlight, garbage, etc.)
5. Enter description and location
6. Upload photo (faces/plates blurred automatically)
7. Allow GPS location access
8. Submit report

**Privacy Note:** All photos are processed client-side before upload. Faces and license plates in the top 35% of images are automatically blurred, and EXIF metadata is stripped.

### For Officers

1. **Login** with officer credentials
2. **View assigned tickets** on dashboard
3. **Filter by status** (submitted, assigned, in_progress, resolved)
4. **Upload repair photo** for verification
5. **System verifies** scene match automatically
6. **Close ticket** when verified

### API Endpoints

Key endpoints:
- `POST /register` - User registration
- `POST /token` - Login (returns JWT)
- `POST /reports` - Submit new report (optional auth)
- `GET /tickets` - List all tickets
- `GET /tickets/{id}` - Get ticket details
- `POST /tickets/{id}/verify` - Submit repair verification
- `GET /stats` - System statistics
- `GET /scorecards` - Department performance metrics

Full API documentation: http://localhost:8000/docs

## 🤖 YOLO Model

The system uses a custom-trained YOLO model for defect classification. The model is located at `models/civic/civic.pt`.

**Supported categories:**
- pothole
- streetlight
- garbage
- water_leak
- live_wire
- drainage
- road_damage

**How it works:**
1. Citizen uploads photo with category hint
2. YOLO analyzes image and detects actual defect
3. If detection differs from hint, system auto-corrects category
4. Confidence score logged for audit trail

## 🔒 Security Features

- **JWT Authentication**: Secure token-based auth
- **Optional Auth**: Citizens can report anonymously
- **Password Hashing**: Bcrypt for password storage
- **EXIF Stripping**: GPS/camera metadata removed
- **Face Blur**: Client-side privacy protection
- **CORS**: Configured for frontend-backend communication

## 🧪 Testing

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app tests/
```

## 🛠️ Configuration

Edit `app/config.py` to customize:
- SLA deadlines by category
- Duplicate detection radius
- Priority weights
- Escalation rules
- Severity mappings

## 📊 Database Schema

**Key tables:**
- `users` - User accounts (citizens, officers)
- `tickets` - Complaint tickets
- `events` - Audit log (append-only)
- `wards` - Geographic boundaries
- `officers` - Officer assignments
- `contractors` - External contractors
- `work_orders` - Contractor work orders

## 🚧 Known Issues

- Ward routing needs proper boundary data (currently uses first ward)
- GPS requires HTTPS in production (use tunnel like ngrok/cloudflared for testing)
- Large YOLO model - consider model quantization for faster inference

## 🗺️ Roadmap

- [ ] Real-time notifications (WebSocket)
- [ ] Mobile app (React Native)
- [ ] Public scoreboard with ward-wise metrics
- [ ] Evidence report PDF generation
- [ ] Integration with municipal GIS systems
- [ ] WhatsApp bot for reporting
- [ ] Multi-language support

## 📝 License

MIT License - see LICENSE file for details

## 👥 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📧 Support

For issues and questions:
- Open an issue on GitHub
- Email: [your-email@example.com]

## 🙏 Acknowledgments

- YOLO by Ultralytics
- FastAPI framework
- React and the amazing frontend ecosystem
- Open source community

---

**Built with ❤️ for better civic governance**
