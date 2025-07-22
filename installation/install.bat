@echo off
set YAML=environment.yml
set SCRIPT=main.py
for /f "tokens=2 delims= " %%A in ('findstr /b /c:"name:" %YAML%') do set ENV_NAME=%%A

call "%USERPROFILE%\anaconda3\Scripts\activate.bat"

:: create or update env
conda env list | findstr /b "%ENV_NAME%" >nul && (
    echo Updating %ENV_NAME% ...
    conda env update -n %ENV_NAME% -f %YAML% --prune
) || (
    echo Creating %ENV_NAME% ...
    conda env create -f %YAML%
)

:: create shortcut batch
set SHORTCUT=%USERPROFILE%\Desktop\RunPTTool.bat
echo @echo off> "%SHORTCUT%"
echo call "%USERPROFILE%\anaconda3\Scripts\activate.bat" %ENV_NAME%>> "%SHORTCUT%"
echo python "%cd%\%SCRIPT%">> "%SHORTCUT%"
echo exit /b>> "%SHORTCUT%"

echo Done. Double-click RunPTTool.bat on your Desktop.
