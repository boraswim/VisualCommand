; Inno Setup 6 script. Built by scripts/build.ps1, which passes /DMyAppVersion=x.y.z
; Produces installer/Output/VisualCommand-Setup-x.y.z.exe

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "VisualCommand"
#define MyAppExe "VisualCommand.exe"

[Setup]
AppId={{8C1F2B7E-4D3A-4F6B-9E21-6A7C3D5B9F10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppName}
VersionInfoVersion={#MyAppVersion}
; Per-user install, no admin prompt: {autopf} becomes %LOCALAPPDATA%\Programs
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=Output
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; A running copy is closed by [Code] below before installing / uninstalling.
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Start {#MyAppName} when I sign in to Windows"; GroupDescription: "Startup:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\VisualCommand\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove the previous build's bundled libraries so upgrades don't mix versions.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Start with Windows. The app's Settings window toggles this same value.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExe}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#MyAppName}"; Flags: deletevalue dontcreatekey; Tasks: not autostart

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM {#MyAppExe} /F', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    SettingsDir := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(SettingsDir) then
      if UninstallSilent or (MsgBox('Also delete your VisualCommand settings and log?' + #13#10 +
         '(Screenshots in Pictures\VisualCommand are kept.)', mbConfirmation, MB_YESNO) = IDYES) then
        DelTree(SettingsDir, True, True, True);
  end;
end;
