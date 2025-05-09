#!/usr/bin/env python3
# Fix SSL certificate issues on macOS

import os
import ssl
import certifi

print(f"Current certifi path: {certifi.where()}")
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Test connection
import urllib.request
import json

try:
    url = "https://storage.googleapis.com"
    print(f"Testing connection to {url}...")
    response = urllib.request.urlopen(url)
    print(f"Connection successful! Status code: {response.status}")
except Exception as e:
    print(f"Error: {e}")