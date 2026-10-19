; Inno Setup script: ONE SignalViewer-Setup.exe that installs everything.
; The installer contains the whole app (Python and all libraries included): installing and
; running need NO internet connection and nothing else installed.
; Build: build.bat installer   (or: iscc installer\SignalViewer.iss after "build.bat portable")

#define AppName "Signal Viewer"
#ifndef AppVersion
  #define AppVersion "1.6.1"
#endif

[Setup]
AppId={{7B6E4C3A-5F2D-4C8B-9A61-3E0D2F5B8C71}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Signal Viewer
DefaultDirName={autopf}\Signal Viewer
DefaultGroupName=Signal Viewer
; install for the current user without administrator rights; an admin may still choose "all users"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=SignalViewer-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
; the licence page of the installer (T32)
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\SignalViewer.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SignalViewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Signal Viewer"; Filename: "{app}\SignalViewer.exe"
Name: "{autodesktop}\Signal Viewer"; Filename: "{app}\SignalViewer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SignalViewer.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; User data (recent files, templates, autosave, cache in %USERPROFILE%\.signalviewer) is kept on uninstall.
