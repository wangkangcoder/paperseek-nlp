@echo off
REM PaperSeek version control helper (ASCII only). Example:
REM   tools\rollback.cmd status
REM   tools\rollback.cmd checkpoint -m "feat: xxx [CHG-010]" --tag v0.2.0-w2 --test
python "%~dp0rollback.py" %*
exit /b %ERRORLEVEL%
