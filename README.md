# Multimodal Misinformation Analyzer

An AI-driven system for detecting fake and manipulated content across text, images, URLs, and documents.

## Features

- Text, URL, image, and document analysis
- OCR text extraction using Tesseract
- NLP sentiment analysis
- ML-based fake/real classification
- Basic deepfake detection+


- PDF report generation
- User authentication with JWT cookie sessions
- Admin dashboard
- MySQL database

## Installation

### Prerequisites

1. Python 3.8+
2. Node.js 14+
3. MySQL 8.0+
4. Tesseract OCR

#### Install Tesseract OCR

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download installer from https://github.com/UB-Mannheim/tesseract/wiki

### Setup

1. **Database Setup**

```bash
mysql -u root -p < database/schema.sql
```

2. **Backend Setup**

```bash
pip install -r requirements.txt
```

Optional enhanced NLP stack:

```bash
pip install -r requirements-advanced-nlp.txt
```

This enables the optional spaCy, NLTK, BERT, and TensorFlow-assisted signals in `ml_pipeline/nlp_module.py`.

3. **Frontend Setup**

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend

```bash
python backend/app.py
```

Backend runs on `http://localhost:5000`

### Start Frontend

```bash
cd frontend
npm start
```

Frontend runs on `http://localhost:3000`

## Deploying to Render

This repo now includes a `Dockerfile` and `render.yaml` so you can deploy it directly from GitHub on Render as a single web service.

### What changed for Render

- React is built during Docker image creation and served by Flask in production
- The API uses same-origin requests in production, so frontend and backend work behind one Render URL
- The backend now supports:
  - `sqlite:///...` by default for simple deployments
  - `postgres://...` or `postgresql://...` via `DATABASE_URL`
  - `mysql://...` via automatic conversion to `mysql+pymysql://...`
- A health endpoint is available at `/api/health`

### Deploy steps

1. Push this repository to GitHub
2. In Render, create a new Blueprint or Web Service from the GitHub repo
3. If using Blueprint, Render will detect `render.yaml`
4. Deploy the service

### Manual Render Web Service setup

If you are creating a normal Render Web Service instead of a Blueprint, use these settings:

- Language: `Docker`
- Branch: your deployed branch such as `develop`
- Region: `Ohio (US East)` if your database is also in Ohio
- Root Directory: leave blank
- Docker Build Context Directory: leave blank or set `.`
- Dockerfile Path: leave blank or set `./Dockerfile`
- Health Check Path: `/api/health`

Recommended environment variables for the web service:

- `SECRET_KEY`
- `DATABASE_URL` = your Render Postgres **Internal Database URL**
- `SEED_DEFAULT_ADMIN=true`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `GROQ_API_KEY` if you want Groq-powered YouTube summaries

Do not use local-only development values on Render such as:

- `DATABASE_URL=mysql+pymysql://root:...@localhost/...`
- `TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe`
- `FLASK_DEBUG=true`
- `FLASK_PORT=5000`
- `FLASK_ENV=development`

### Free-tier deployment note

The included `render.yaml` is configured for a free web service and a free Render Postgres database so you can deploy without paid resources for demo/testing use. During Blueprint creation, Render will prompt you to enter:

- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`

Keep in mind:

- Free web services can spin down when idle, so the first request after inactivity may be slow
- Free Postgres is suitable for hobby/demo use but is not the same as a production-grade paid database plan

### Recommended environment variables

- `SECRET_KEY`: generated automatically by `render.yaml`
- `DATABASE_URL`: optional, but recommended for persistent data
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `SEED_DEFAULT_ADMIN=true` only if you intentionally want Render to create an admin account on boot
- `GROQ_API_KEY` for optional Groq-based YouTube summarization

### Important note about persistence

If you do not set `DATABASE_URL`, the app uses SQLite inside the container so deployment is easy, but that data is not durable across fresh Render deploys/restarts. For production use, connect a managed database and set `DATABASE_URL`.

## Default Admin Credentials

If `SEED_DEFAULT_ADMIN=true`, the app seeds this admin user on startup:

- Email: admin@example.com
- Password: admin123

**IMPORTANT: Change these credentials in production!**

## Usage

1. Register/Login at `http://localhost:3000`
2. Upload content (text, URL, YouTube, image, screenshot, or document)
3. Receive analysis with prediction, confidence score, and manipulation score
4. Download PDF report
5. Admin can view all inputs and reports at `/admin`

## API Endpoints

- `POST /api/register` - Register new user
- `POST /api/login` - Login user
- `GET /api/session` - Read the current cookie-backed session
- `POST /api/logout` - Invalidate the current session and clear cookies
- `POST /api/analyze` - Analyze content (requires auth)
- `GET /api/report/<id>` - Download report (requires auth)
- `GET /api/admin/inputs` - Get all inputs (admin only)
- `GET /api/admin/reports` - Get all reports (admin only)

## Project Structure

```
multimodal-misinformation-analyzer/
├── backend/              # Flask API
│   ├── app.py           # Main application
│   └── models.py        # Database models
├── ml_pipeline/         # ML modules
│   ├── analyzer.py      # Main analyzer
│   ├── text_classifier.py  # TF-IDF + LogisticRegression
│   ├── nlp_module.py    # Sentiment analysis
│   ├── ocr_module.py    # Tesseract OCR
│   ├── deepfake_detector.py  # Image manipulation detection
│   └── report_generator.py   # PDF generation
├── database/
│   └── schema.sql       # MySQL schema
├── frontend/            # React application
│   └── src/
│       └── components/  # React components
├── uploads/             # Uploaded files
└── reports/             # Generated reports
```

## Chapter 7: Security And Session Management

The authentication flow now uses JWT access tokens stored in HTTPOnly cookies instead of exposing session tokens to browser JavaScript.

### Cookie settings

- `JWT_COOKIE_HTTPONLY=True`
- `JWT_COOKIE_SAMESITE='Lax'`
- `JWT_ACCESS_TOKEN_EXPIRES=1 hour`
- `JWT_COOKIE_SECURE=True` in production

For local development, `JWT_COOKIE_SECURE` can be set to `false` so cookies continue to work over plain `http://localhost`.

### Session lifecycle

- `/api/login` creates a JWT session and sets the access cookie
- `/api/session` lets the frontend restore the authenticated user after refresh
- `/api/logout` revokes the current token `jti`, stores it in the blocklist table, and clears the cookies
- Revoked or expired cookies are rejected server-side

### Frontend security changes

- The React app no longer stores auth tokens in `localStorage`
- Browser requests use cookie-backed sessions with `credentials: 'include'`
- Logout clears both the server session and cached local user state

### Operational notes

- Change `SECRET_KEY` and `JWT_SECRET_KEY` in production
- Change the seeded admin credentials before public deployment
- Use HTTPS in production so secure cookies are always transmitted safely
- Keep CORS restricted to trusted origins when deploying frontend and backend separately

## Future Enhancements

- Multilingual NLP support
- Advanced deepfake detection using CNNs
- Real-time monitoring
- Browser extension
- Advanced ML models (BERT, RoBERTa)

## License

Educational project - use at your own risk
