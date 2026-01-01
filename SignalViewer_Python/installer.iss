; Signal Viewer Pro - Inno Setup Script
; ======================================
; Creates a professional Windows installer
;
; Prerequisites:
; 1. Build the application first: build.bat
; 2. Download Inno Setup: https://jrsoftware.org/isdl.php
; 3. Open this file in Inno Setup Compiler
; 4. Click Build > Compile
;
; Output: SignalViewerProSetup.exe

#define MyAppName "Signal Viewer Pro"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Signal Viewer Team"
#define MyAppURL "https://github.com/your-username/signal-viewer-pro"
#define MyAppExeName "SignalViewer.exe"
#define MyAppAssocName "CSV Signal Data"
#define MyAppAssocExt ".csv"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
; Application information
AppId={{A8E5C9D4-B3F2-4E7A-9C1D-2F6E8A0B4C3D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation paths
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Installer behavior
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer_output
OutputBaseFilename=SignalViewerProSetup-{#MyAppVersion}
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files from PyInstaller output
Source: "dist\SignalViewer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Quick Launch (optional, for older Windows)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; File association (optional - associate with CSV files)
; Uncomment if you want Signal Viewer to be an option for opening CSV files
; Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppAssocKey}"; ValueData: ""; Flags: uninsdeletevalue
; Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; Flags: uninsdeletekey
; Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
; Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Code]
// Check if .NET Framework or Visual C++ Runtime is needed
function InitializeSetup: Boolean;
begin
  Result := True;
  // Add any pre-installation checks here
end;

// Custom messages
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption := 
    'This will install Signal Viewer Pro on your computer.' + #13#10 + #13#10 +
    'Signal Viewer Pro is a professional signal visualization and analysis tool ' +
    'for analyzing CSV data with multiple signals, comparing waveforms, and ' +
    'creating publication-ready plots.' + #13#10 + #13#10 +
    'Click Next to continue, or Cancel to exit Setup.';
end;
