#!/usr/bin/env python
import sys
import os
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent
sys.path.insert(0, str(workspace_root))

print("=" * 60)
print("API DIAGNOSTIC TEST")
print("=" * 60)

# 1. Check environment variables
print("\n✓ Environment Variables:")
from dotenv import load_dotenv
load_dotenv(workspace_root / '.env')

db_url = os.getenv('DATABASE_URL')
print(f"  - DATABASE_URL: {db_url}")
print(f"  - TESSERACT_PATH: {os.getenv('TESSERACT_PATH')}")

# 2. Check database connection
print("\n✓ Database Connection:")
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    from backend.models import db, User, Input, Report
    from backend.app import app
    
    with app.app_context():
        # Try to query users table
        users = User.query.all()
        print(f"  ✓ Database connected! Users in DB: {len(users)}")
except Exception as e:
    print(f"  ✗ Database connection failed: {e}")

# 3. Check ML pipeline
print("\n✓ ML Pipeline:")
try:
    from ml_pipeline.analyzer import analyze_content
    print("  ✓ Analyzer loaded")
    
    # Test text analysis
    result = analyze_content('text', 'This is a test message', None)
    print(f"  ✓ Text analysis works: {result['prediction']}")
except Exception as e:
    print(f"  ✗ ML pipeline failed: {e}")

# 4. Check PDF generation
print("\n✓ PDF Generation:")
try:
    from ml_pipeline.report_generator import generate_pdf_report
    test_result = {
        'prediction': 'Test',
        'confidence': 0.5,
        'manipulation_score': 0.0,
        'sentiment': 'neutral',
        'explanation': 'Test',
        'extracted_text': ''
    }
    report_path = generate_pdf_report(test_result, 999)
    print(f"  ✓ PDF generation works")
    if os.path.exists(report_path):
        os.remove(report_path)
except Exception as e:
    print(f"  ✗ PDF generation failed: {e}")

# 5. Check file system
print("\n✓ File System:")
try:
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    print("  ✓ Upload/Reports folders exist")
except Exception as e:
    print(f"  ✗ File system error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTICS COMPLETE")
print("=" * 60)
