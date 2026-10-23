; Per-user install: Python, native dependencies, and model are already bundled.
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
[Setup]
AppId={{A95D64A6-375C-4E89-965B-A5C981A0454E}
AppName=Now Playing
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Now Playing
DefaultGroupName=Now Playing
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=Now-Playing-Windows-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Now Playing.exe
CloseApplications=yes
SetupLogging=yes

[Files]
Source: "..\dist\Now Playing\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "WINDOWS-README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Now Playing"; Filename: "{app}\Now Playing.exe"
Name: "{autodesktop}\Now Playing"; Filename: "{app}\Now Playing.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\Now Playing.exe"; Description: "Open Now Playing"; Flags: nowait postinstall skipifsilent

; Album history is under LOCALAPPDATA\NowPlaying and is deliberately retained
; on uninstall and upgrades. Never add it to UninstallDelete.
