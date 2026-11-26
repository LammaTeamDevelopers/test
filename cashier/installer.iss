; اختياري: ملف Setup واحد (Inno Setup 6) - شغّله بعد build.bat
[Setup]
AppName=Cashier Pro
AppVersion=1.0
DefaultDirName={autopf}\CashierPro
DefaultGroupName=Cashier Pro
OutputBaseFilename=CashierPro-Setup
OutputDir=dist
Compression=lzma
SolidCompression=yes
MinVersion=6.1
PrivilegesRequired=admin
[Files]
Source: "dist\CashierPro.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Cashier Pro"; Filename: "{app}\CashierPro.exe"
Name: "{commondesktop}\Cashier Pro"; Filename: "{app}\CashierPro.exe"
[Run]
Filename: "{app}\CashierPro.exe"; Description: "تشغيل البرنامج"; Flags: nowait postinstall skipifsilent
