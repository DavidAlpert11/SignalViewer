; Inno Setup script: ONE SignalViewer-Setup.exe that installs everything.
; The installer contains the whole app (Python and all libraries included): installing and
; running need NO internet connection and nothing else installed.
; Build: build.bat installer   (or: iscc installer\SignalViewer.iss after "build.bat portable")

#define AppName "Signal Viewer"
#ifndef AppVersion
  #define AppVersion "1.12.0"
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
; T54: "Open with" entries for the data files (Explorer refreshes its icons and menus)
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[CustomMessages]
; (this file is UTF-8 WITH a byte-order mark: Inno Setup reads it as ANSI without one - the Hebrew lines)
english.OpenWith=Offer Signal Viewer in "Open with" for data files (.bin, .tlog, .ulg, .mcap, .mat, .csv, .parquet, .h5) and open sessions (.svsession) with it
hebrew.OpenWith=הצעת Signal Viewer ב"פתח באמצעות" לקובצי נתונים (.bin, .tlog, .ulg, .mcap, .mat, .csv, .parquet, .h5) ופתיחת סשנים (.svsession) בו
english.DataFile=Signal Viewer data file
hebrew.DataFile=קובץ נתונים של Signal Viewer

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "openwith"; Description: "{cm:OpenWith}"

[Files]
Source: "..\dist\SignalViewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


; T54: files opened from Explorer go to the running app (run.py hands them over). "Open with"
; only - the user's default programs are not changed - except .svsession, which is ours.
; HKA = per user for a per-user install, all users for an all-users install.
[Registry]
Root: HKA; Subkey: "Software\Classes\SignalViewer.DataFile"; ValueType: string; ValueName: ""; ValueData: "{cm:DataFile}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\SignalViewer.DataFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\SignalViewer.exe,0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\SignalViewer.DataFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SignalViewer.exe"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Signal Viewer"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SignalViewer.exe"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.bin\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".bin"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.tlog\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".tlog"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ulg\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".ulg"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mcap\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".mcap"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mat\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".mat"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.csv\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".csv"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.parquet\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".parquet"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.pq\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".pq"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.h5\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".h5"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.hdf5\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".hdf5"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.svsession\OpenWithProgids"; ValueType: string; ValueName: "SignalViewer.DataFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\SignalViewer.exe\SupportedTypes"; ValueType: string; ValueName: ".svsession"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.svsession"; ValueType: string; ValueName: ""; ValueData: "SignalViewer.DataFile"; Flags: uninsdeletevalue createvalueifdoesntexist; Tasks: openwith

[Icons]
Name: "{group}\Signal Viewer"; Filename: "{app}\SignalViewer.exe"
Name: "{autodesktop}\Signal Viewer"; Filename: "{app}\SignalViewer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SignalViewer.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; User data (recent files, templates, autosave, cache in %USERPROFILE%\.signalviewer) is kept on uninstall.
