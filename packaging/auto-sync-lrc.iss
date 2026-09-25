; Inno Setup script: wraps the PyInstaller output folder into a single Setup.exe.
; Build: ISCC.exe /DAppVersion=0.2.0 packaging\auto-sync-lrc.iss   (run from the repo root)

#define AppName "Auto-sync-LRC"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Auto-sync-LRC"
#endif

[Setup]
AppId={{6E1C2B7A-3D54-4C0E-9B5A-2F7D8A41C9E3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=luoarting-hub
AppPublisherURL=https://github.com/luoarting-hub/Auto-sync-LRC
AppSupportURL=https://github.com/luoarting-hub/Auto-sync-LRC/issues
; Installs for the current user only, so Windows never asks for an administrator password.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\installer-out
OutputBaseFilename=Auto-sync-LRC-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Auto-sync-LRC.exe
LicenseFile=..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a shortcut on the desktop"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Auto-sync-LRC.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Auto-sync-LRC.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Auto-sync-LRC.exe"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent
