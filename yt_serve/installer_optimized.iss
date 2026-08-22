; Playlist Manager - Optimized Inno Setup Installer Script
; This creates a professional Windows installer with embedded frontend (no Node.js required)

#define MyAppName "Playlist Manager"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Your Name"
#define MyAppURL "https://github.com/YOUR_USERNAME/playlist-manager"
#define MyAppExeName "PlaylistManager_Optimized.exe"
#define PythonVersion "3.12"

[Setup]
; Basic app information
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Output
OutputDir=installer_output
OutputBaseFilename=PlaylistManager_Optimized_Setup
SetupIconFile=app_icon.ico
Compression=lzma
SolidCompression=yes

; Privileges (reduced - no longer need admin for Node.js)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog

; Wizard appearance
WizardStyle=modern
DisableProgramGroupPage=yes
DisableWelcomePage=no

; License and info
LicenseFile=LICENSE
InfoBeforeFile=INSTALL_INFO.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application executable (optimized launcher)
Source: "dist\PlaylistManager_Optimized.exe"; DestDir: "{app}"; Flags: ignoreversion

; Application files (backend with embedded frontend)
Source: "yt_serve\backend\*"; DestDir: "{app}\yt_serve\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "yt_serve\downloads\*"; DestDir: "{app}\yt_serve\downloads"; Flags: ignoreversion recursesubdirs createallsubdirs; Attribs: hidden

; Documentation
Source: "yt_serve\DOCS\*"; DestDir: "{app}\DOCS"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "yt_serve\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

; Legacy tools (for migration)
Source: "yt_playlist_audio_tools.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "migrate_playlists.py"; DestDir: "{app}"; Flags: ignoreversion

; Portable Python (embed version - ONLY Python needed now!)
Source: "portable\python\*"; DestDir: "{app}\portable\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; Configuration templates
Source: "yt_serve\backend\.env.example"; DestDir: "{app}\yt_serve\backend"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Run]
; Setup Python environment (much faster now - no Node.js!)
Filename: "{app}\setup_python_only.bat"; Description: "Setup Python environment (required)"; Flags: postinstall runhidden waituntilterminated
; Offer to launch the app
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[Code]
var
  DownloadPage: TDownloadWizardPage;
  
function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if Progress = ProgressMax then
    Log(Format('Successfully downloaded %s', [FileName]));
  Result := True;
end;

procedure InitializeWizard;
begin
  // Download page for portable Python (if needed)
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = wpReady then begin
    DownloadPage.Clear;
    // Could add Python download here if not bundled
    // DownloadPage.Add('https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip', 'python-embed.zip', '');
    // DownloadPage.Download;
    Result := True;
  end else
    Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // Create setup script for Python-only environment
    SaveStringToFile(ExpandConstant('{app}\setup_python_only.bat'), 
      '@echo off' + #13#10 +
      'echo Setting up Python environment...' + #13#10 +
      'cd /d "%~dp0"' + #13#10 +
      'if not exist "yt_serve\backend\venv" (' + #13#10 +
      '  echo Creating Python virtual environment...' + #13#10 +
      '  python -m venv yt_serve\backend\venv' + #13#10 +
      '  if errorlevel 1 (' + #13#10 +
      '    echo Using portable Python...' + #13#10 +
      '    portable\python\python.exe -m venv yt_serve\backend\venv' + #13#10 +
      '  )' + #13#10 +
      ')' + #13#10 +
      'echo Installing Python dependencies...' + #13#10 +
      'yt_serve\backend\venv\Scripts\pip.exe install -r yt_serve\backend\requirements.txt' + #13#10 +
      'if not exist "yt_serve\backend\.env" (' + #13#10 +
      '  echo Creating default configuration...' + #13#10 +
      '  copy "yt_serve\backend\.env.example" "yt_serve\backend\.env"' + #13#10 +
      ')' + #13#10 +
      'echo Setup complete!' + #13#10, 
      False);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\yt_serve\backend\venv"
Type: filesandordirs; Name: "{app}\yt_serve\backend\*.db"
Type: filesandordirs; Name: "{app}\yt_serve\backend\*.log"
Type: filesandordirs; Name: "{app}\yt_serve\downloads"
Type: files; Name: "{app}\setup_python_only.bat"
