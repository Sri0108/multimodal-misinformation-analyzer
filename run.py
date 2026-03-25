#!/usr/bin/env python
"""
Entry point for the Multimodal Misinformation Analyzer backend.
Run from project root: python run.py
"""
import sys
import os
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    from backend.app import app
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    print(f"Starting Multimodal Misinformation Analyzer...")
    print(f"  - Host: {host}")
    print(f"  - Port: {port}")
    print(f"  - Debug: {debug}")
    print(f"\nAPI available at: http://localhost:{port}")
    print(f"Documentation: http://localhost:{port}/\n")
    
    app.run(host=host, port=port, debug=debug)
