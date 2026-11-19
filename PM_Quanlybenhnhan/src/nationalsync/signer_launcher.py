"""Wrap the PowerShell signer so a doctor can start it with a double-click."""

from __future__ import annotations

SIGNER_DOWNLOAD_NAME = "Ky_USB_ViettelCA.cmd"
_MARKER = "###VIETTEL_CA_SIGNER###"

# ASCII only. cmd.exe reads this header with the system code page.
_HEADER = """\
@echo off
chcp 65001 >nul
setlocal
set "SIGNER_CMD=%~f0"
title Ky USB Viettel-CA
echo Dang mo chuong trinh ky USB.
echo Hay de cua so nay mo. Khi dong bo, hop nhap PIN se hien ra.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:SIGNER_CMD; $text=[IO.File]::ReadAllText($p,[Text.Encoding]::UTF8); $mark='###VIETTEL_CA_'+'SIGNER###'; $i=$text.IndexOf($mark); if($i -lt 0){ throw 'missing script' }; $script=$text.Substring($i+$mark.Length).TrimStart([char]13,[char]10); Invoke-Expression $script"
echo.
echo Chuong trinh da dung. Nhan phim bat ky de dong cua so.
pause
exit /b
"""


def build_signer_command(script: str) -> bytes:
    """Return a .cmd file: double-click runs the PowerShell signer."""
    if _MARKER in script:
        raise ValueError("signer script contains the launcher marker")
    normalized = script.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    header = _HEADER.replace("\r\n", "\n").replace("\r", "\n")
    text = f"{header}{_MARKER}\n{normalized}\n".replace("\n", "\r\n")
    return text.encode("utf-8")
