#!/usr/bin/env python
import requests
import json
import sys
import os
from pathlib import Path

workspace_root = Path(__file__).parent
sys.path.insert(0, str(workspace_root))

from dotenv import load_dotenv
load_dotenv(workspace_root / '.env')

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings()

BASE_URL = "http://localhost:5000"

print("=" * 60)
print("API TEST - Multimodal Misinformation Analyzer")
print("=" * 60)

# Step 1: Register a test user
print("\n[1] REGISTERING TEST USER...")
try:
    resp = requests.post(f"{BASE_URL}/api/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpass123"
    })
    print(f"    Status: {resp.status_code}")
    print(f"    Response: {resp.text}")
except Exception as e:
    print(f"    Error: {e}")

# Step 2: Login
print("\n[2] LOGGING IN...")
try:
    resp = requests.post(f"{BASE_URL}/api/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    print(f"    Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        token = data.get('token')
        print(f"    ✓ Got JWT token: {token[:20]}...")
    else:
        print(f"    Response: {resp.text}")
        token = None
except Exception as e:
    print(f"    Error: {e}")
    token = None

# Step 3: Test analyze endpoint
if token:
    print("\n[3] TESTING /api/analyze (TEXT)...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(f"{BASE_URL}/api/analyze", 
            json={
                "content_type": "text",
                "content": "Breaking news: Scientists discover shocking secret!"
            },
            headers=headers
        )
        print(f"    Status: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json()
            print(f"    ✓ Analysis successful!")
            print(f"    Prediction: {result['result']['prediction']}")
            print(f"    Confidence: {result['result']['confidence']:.2%}")
        else:
            print(f"    Error: {resp.text}")
    except Exception as e:
        print(f"    Error: {e}")
else:
    print("\n[!] Cannot test /api/analyze - no JWT token obtained")

print("\n" + "=" * 60)
