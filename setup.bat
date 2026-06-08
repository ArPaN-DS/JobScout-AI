@echo off
:: JobScout-AI Windows Setup Script
:: Automates virtual environment setup, package installations, secret configuration, and admin database initializations.

echo ===================================================
echo           JobScout-AI Windows Onboarding           
echo ===================================================

:: 1. Check Python Version
echo 🔍 Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python 3.11+ and try again.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
if not exist "job_finder_env" (
    echo 📦 Creating virtual environment 'job_finder_env'...
    python -m venv job_finder_env
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo 📦 Virtual environment 'job_finder_env' already exists.
)

:: 3. Activate Virtual Environment
echo 🔌 Activating virtual environment...
call .\job_finder_env\Scripts\activate
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: 4. Upgrade Pip and Install Dependencies
echo 📥 Upgrading pip...
python -m pip install --upgrade pip
echo 📥 Installing project dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

:: 5. Generate Cryptographic Keys
if exist "generate_keys.py" (
    echo 🔑 Configuring secret keys...
    python generate_keys.py
) else (
    echo [WARNING] generate_keys.py not found. Skipping automated key generation.
)

:: 6. Apply Database Migrations
echo 🗄️ Running database migrations...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Database migrations failed.
    pause
    exit /b 1
)

:: 7. Create Default Admin User Non-Interactively
echo 👤 Setting up default developer admin user...
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"
if errorlevel 1 (
    echo [WARNING] Failed to configure superuser automatically. You may need to run 'python manage.py createsuperuser' manually.
) else (
    echo [SUCCESS] Default developer admin configured (Username: admin, Password: admin123).
)

echo ===================================================
echo 🎉 Setup Completed Successfully!
echo ===================================================
echo To run JobScout-AI, run two terminals side-by-side:
echo.
echo   [Terminal 1: Web Interface Server]
echo     .\job_finder_env\Scripts\activate
echo     python manage.py runserver
echo.
echo   [Terminal 2: Background Task Worker]
echo     .\job_finder_env\Scripts\activate
echo     python manage.py qcluster
echo.
echo Dashboard URL: http://127.0.0.1:8000/
echo Credentials: admin / admin123
echo ===================================================
pause
