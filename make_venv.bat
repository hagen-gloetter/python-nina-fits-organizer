# Setup Script für Astro-Projekt
Write-Host "Setting up Astro Python Environment..." -ForegroundColor Green

# Venv erstellen
python -m venv astro_env

# Aktivieren
.\astro_env\Scripts\Activate.ps1

# Pakete installieren
pip install astropy numpy

Write-Host "✅ Setup completed! Virtual environment is ready." -ForegroundColor Green
Write-Host "Use: .\astro_env\Scripts\Activate.ps1" -ForegroundColor Yellow

.\astro_env\Scripts\activate