; Script de Instalación Inno Setup para COBALTO HUB C4I
#define MyAppName "COBALTO HUB"
#define MyAppVersion "12.1"
#define MyAppPublisher "COBALTO Intelligence Team"
#define MyAppExeName "CobaltoHUB.exe"

[Setup]
AppId={{C0BA170-C41-489A-901B-COBALTO121}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=C:\\Users\\Ulianov\\Documents\\COBORO\\COBALTO\\dist_installer
OutputBaseFilename=Setup_CobaltoHUB_v12.1
SetupIconFile=C:\\Users\\Ulianov\\Documents\\COBORO\\COBALTO\\static\\icons\\cobalto.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "C:\\Users\\Ulianov\\Documents\\COBORO\\COBALTO\\dist\\CobaltoHUB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
