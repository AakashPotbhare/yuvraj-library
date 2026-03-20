import os

DATABASE_PATH     = os.environ.get("DATABASE_PATH", "library.db")
DEFAULT_LOAN_DAYS = int(os.environ.get("DEFAULT_LOAN_DAYS", "15"))
APP_NAME          = "Yuvraj Library"
SECRET_KEY        = os.environ.get("SECRET_KEY", "yuvraj-library-secret-change-in-production")

# Email config for password recovery
MAIL_HOST     = os.environ.get("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT     = int(os.environ.get("MAIL_PORT", "587"))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")

# Supabase
SUPABASE_URL         = os.environ.get("SUPABASE_URL", "https://ksclhcogjisjcmyinbiz.supabase.co")
SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtzY2xoY29namlzamNteWluYml6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQwMjUxNjYsImV4cCI6MjA4OTYwMTE2Nn0.Olsqr-70-n6rh5DmAd5sL7hXUPmt_Zdw3zmm41HEDxU")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
