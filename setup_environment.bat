@echo off


set VENV_NAME=.venv_%COMPUTERNAME%


if exist "%VENV_NAME%" (
    echo [INFO] %VENV_NAME% already exists 
) else (
    echo [INFO] creating %VENV_NAME%
    python -m venv %VENV_NAME%
)


call %VENV_NAME%\Scripts\activate 

if exist "requirements.txt" (
    echo [INFO] Installing packages from requirements.txt
    pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not found, skipping package installation
)

pause