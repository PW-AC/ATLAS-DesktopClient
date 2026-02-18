; Inno Setup Script für ACENCIA ATLAS
; Erstellt einen professionellen Windows Installer

#define MyAppName "ACENCIA ATLAS"
#define MyAppVersion "2.1.3"
#define MyAppPublisher "ACENCIA GmbH"
#define MyAppURL "https://acencia.info"
#define MyAppExeName "ACENCIA-ATLAS.exe"

[Setup]
; App-Informationen
AppId={{8F9D5E3A-1234-5678-9ABC-DEF012345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt
OutputDir=Output
OutputBaseFilename=ACENCIA-ATLAS-Setup
SetupIconFile=src\ui\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; Single-Instance + Update-Schutz
; Installer wartet bis die laufende App geschlossen ist
AppMutex=ACENCIA_ATLAS_SINGLE_INSTANCE
CloseApplications=force
CloseApplicationsFilter=*.exe

; Berechtigungen
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Architektur
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "dist\ACENCIA-ATLAS\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ACENCIA-ATLAS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "src\ui\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Prüfe ob .NET installiert ist (falls benötigt)
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
