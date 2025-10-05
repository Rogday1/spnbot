@echo off
cd /d "%~dp0"
set BOT_TOKEN=7569052280:AAET0O8dn0gPBANgjn3IHTA3ekk1mV7gaIc
set DATABASE_URL=sqlite+aiosqlite:///./spin_bot.db
set DEBUG=true
set WEBAPP_PUBLIC_URL=http://localhost:8001
python main.py
pause

