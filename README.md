# Multimodal Misinformation Analyzer

An AI-driven system for detecting fake and manipulated content across text, images, URLs, and documents.

## Features

- Text, URL, image, and document analysis
- OCR text extraction using Tesseract
- NLP sentiment analysis
- ML-based fake/real classification
- Basic deepfake detection+


- PDF report generation
- User authentication (JWT)
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

### Important note about persistence

If you do not set `DATABASE_URL`, the app uses SQLite inside the container so deployment is easy, but that data is not durable across fresh Render deploys/restarts. For production use, connect a managed database and set `DATABASE_URL`.

## Default Admin Credentials

If `SEED_DEFAULT_ADMIN=true`, the app seeds this admin user on startup:

- Email: admin@example.com
- Password: admin123

**IMPORTANT: Change these credentials in production!**

## Usage

1. Register/Login at `http://localhost:3000`
2. Upload content (text, URL, image, or document)
3. Receive analysis with prediction, confidence score, and manipulation score
4. Download PDF report
5. Admin can view all inputs and reports at `/admin`

## API Endpoints

- `POST /api/register` - Register new user
- `POST /api/login` - Login user
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

## Security Notes

- Change default SECRET_KEY and JWT_SECRET_KEY
- Update admin password
- Use HTTPS in production
- Set up proper database credentials
- Enable CORS only for trusted domains

## Future Enhancements

- Multilingual NLP support
- Advanced deepfake detection using CNNs
- Real-time monitoring
- Browser extension
- Advanced ML models (BERT, RoBERTa)

## License

Educational project - use at your own risk
