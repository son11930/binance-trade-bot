#!/bin/bash
echo "Installing required dependencies..."
pip install -r requirements.txt >/dev/null 2>&1
echo ""
python3 generate_hash.py
echo ""
read -p "Press any key to continue..."
