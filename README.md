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

## Default Admin Credentials

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
