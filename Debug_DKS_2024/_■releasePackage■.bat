@echo off

del *.pdb
del *.xml

del DakhoasoSoft\TextFile1.txt
del DakhoasoSoft.vshost.exe
del DakhoasoSoft.vshost.exe.manifest
del DakhoasoSoft.pdb
del DakhoasoSoft.vshost.exe.config
del DakhoasoSoft.vshost.application

rmdir de /s /q
rmdir es /s /q
rmdir ja /s /q
rmdir ru /s /q

move *.exe DakhoasoSoft\
move *.config DakhoasoSoft\
move *.dll DakhoasoSoft\
move *.json DakhoasoSoft\
move *.application DakhoasoSoft\
move *.exe.manifest DakhoasoSoft\

del _?*releasePackage?*.bat
pause