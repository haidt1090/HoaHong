; Supported custom NSIS installer. Generate the uninstaller on the user's Windows
; machine during installation, so cross-building does not require running EXEs.
!include "MUI2.nsh"
!include "LogicLib.nsh"
Unicode true
Name "InBaoCao"
InstallDir "$LOCALAPPDATA\Programs\InBaoCao"
InstallDirRegKey HKCU "Software\HoaHong\InBaoCao" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Vietnamese"

Section "InBaoCao" MainSection
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${BUILD_RESOURCES_DIR}\..\release\win-unpacked\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\InBaoCao"
  CreateShortcut "$SMPROGRAMS\InBaoCao\InBaoCao.lnk" "$INSTDIR\InBaoCao.exe"
  CreateShortcut "$DESKTOP\InBaoCao.lnk" "$INSTDIR\InBaoCao.exe"
  WriteRegStr HKCU "Software\HoaHong\InBaoCao" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "DisplayName" "InBaoCao"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "Publisher" "HoaHong"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "DisplayIcon" "$INSTDIR\InBaoCao.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\InBaoCao.lnk"
  Delete "$SMPROGRAMS\InBaoCao\InBaoCao.lnk"
  RMDir "$SMPROGRAMS\InBaoCao"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\InBaoCao"
  DeleteRegKey HKCU "Software\HoaHong\InBaoCao"
  ; Remove only known app files. Preserve the template database in AppData.
  Delete "$INSTDIR\InBaoCao.exe"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\chrome_100_percent.pak"
  Delete "$INSTDIR\chrome_200_percent.pak"
  Delete "$INSTDIR\d3dcompiler_47.dll"
  Delete "$INSTDIR\ffmpeg.dll"
  Delete "$INSTDIR\icudtl.dat"
  Delete "$INSTDIR\libEGL.dll"
  Delete "$INSTDIR\libGLESv2.dll"
  Delete "$INSTDIR\resources.pak"
  Delete "$INSTDIR\snapshot_blob.bin"
  Delete "$INSTDIR\v8_context_snapshot.bin"
  Delete "$INSTDIR\vk_swiftshader.dll"
  Delete "$INSTDIR\vk_swiftshader_icd.json"
  Delete "$INSTDIR\vulkan-1.dll"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\LICENSE.electron.txt"
  Delete "$INSTDIR\LICENSES.chromium.html"
  Delete "$INSTDIR\locales\*.pak"
  RMDir "$INSTDIR\locales"
  Delete "$INSTDIR\resources\app.asar"
  Delete "$INSTDIR\resources\app-update.yml"
  Delete "$INSTDIR\resources\elevate.exe"
  RMDir /r "$INSTDIR\resources\app.asar.unpacked"
  RMDir "$INSTDIR\resources"
  RMDir "$INSTDIR"
SectionEnd
