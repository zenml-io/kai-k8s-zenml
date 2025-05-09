#!/bin/bash
# Run simple.py with SSL certificate fix

# Set SSL certificate paths
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
export REQUESTS_CA_BUNDLE=$(python -c "import certifi; print(certifi.where())")

# Run the pipeline
python simple.py