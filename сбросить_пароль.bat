@echo off
chcp 65001 >nul
echo ========================================================
echo             СБРОС ПАРОЛЯ УЧИТЕЛЯ КУРСА
echo ========================================================
echo.

set "PW_FILE=%USERPROFILE%\.kurs-server\teacher_password.json"

if exist "%PW_FILE%" (
    del /f /q "%PW_FILE%"
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось удалить файл пароля: %PW_FILE%
        echo Закройте программы, использующие этот файл, или запустите от имени администратора.
    ) else if exist "%PW_FILE%" (
        echo [ОШИБКА] Файл пароля не удалён: %PW_FILE%
    ) else (
        echo [УСПЕШНО] Пароль учителя сброшен!
        echo.
        echo Теперь откройте в браузере страницу:
        echo http://localhost:8000/teacher
        echo и введите новый пароль.
    )
) else (
    echo Пароль уже не установлен (файл не найден).
    echo Откройте http://localhost:8000/teacher и задайте пароль.
)

echo.
pause
