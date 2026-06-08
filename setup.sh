#!/usr/bin/env bash
# JobScout-AI Unix/macOS Setup Script
# Automates virtual environment setup, package installations, secret configuration, and admin database initializations.

set -e # Exit immediately on error

echo "==================================================="
echo "          JobScout-AI Unix/macOS Onboarding"
echo "==================================================="

# 1. Check Python Version
echo "🔍 Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not added to your system PATH."
    echo "Please install Python 3.11+ and try again."
    exit 1
fi

# Ensure Python version is 3.11+
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.11"

if [ "$(echo -e "$PYTHON_VERSION\n$REQUIRED_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "[WARNING] JobScout-AI officially supports Python 3.11+. You are running Python $PYTHON_VERSION."
fi

# 2. Create Virtual Environment
if [ ! -d "job_finder_env" ]; then
    echo "📦 Creating virtual environment 'job_finder_env'..."
    python3 -m venv job_finder_env
else
    echo "📦 Virtual environment 'job_finder_env' already exists."
fi

# 3. Activate Virtual Environment
echo "🔌 Activating virtual environment..."
source job_finder_env/bin/activate

# 4. Upgrade Pip and Install Dependencies
echo "📥 Upgrading pip..."
pip install --upgrade pip
echo "📥 Installing project dependencies..."
pip install -r requirements.txt

# 5. Generate Cryptographic Keys
if [ -f "generate_keys.py" ]; then
    echo "🔑 Configuring secret keys..."
    python3 generate_keys.py
else
    echo "[WARNING] generate_keys.py not found. Skipping automated key generation."
fi

# 6. Apply Database Migrations
echo "🗄️ Running database migrations..."
python3 manage.py migrate

# 7. Create Default Admin User Non-Interactively
echo "👤 Setting up default developer admin user..."
python3 manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')" || {
    echo "[WARNING] Failed to configure superuser automatically. You may need to run 'python manage.py createsuperuser' manually."
}

echo "==================================================="
echo "🎉 Setup Completed Successfully!"
echo "==================================================="
echo "To run JobScout-AI, run two terminals side-by-side:"
echo ""
echo "  [Terminal 1: Web Interface Server]"
echo "    source job_finder_env/bin/activate"
echo "    python manage.py runserver"
echo ""
echo "  [Terminal 2: Background Task Worker]"
echo "    source job_finder_env/bin/activate"
echo "    python manage.py qcluster"
echo ""
echo "Dashboard URL: http://127.0.0.1:8000/"
echo "Credentials: admin / admin123"
echo "==================================================="
