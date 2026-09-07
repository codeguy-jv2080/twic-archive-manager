; Packages the canonical portable build without relocating or deleting it.
#ifndef ProjectRoot
  #define ProjectRoot ".."
#endif
#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build_installer.ps1
#endif
#define AppName "TWIC Archive Manager"
#define AppExe "TWIC Archive Manager.exe"

[Setup]
AppId={{53F7B8E5-A88E-42EF-B6C1-9E498FE1A7CE}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ProjectRoot}\dist
OutputBaseFilename=TWIC-Archive-Manager-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
AppMutex=Global\TWICArchiveManager.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#ProjectRoot}\dist\TWIC Archive Manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function TargetsThisInstallation(Task: Variant): Boolean;
var
  Actions, Action: Variant;
  I: Integer;
  TaskPath: String;
begin
  Result := False;
  if Pos('TWIC Archive Manager - ', String(Task.Name)) <> 1 then
    Exit;
  Actions := Task.Definition.Actions;
  for I := 1 to Actions.Count do
  begin
    Action := Actions.Item(I);
    try
      TaskPath := RemoveQuotes(Trim(String(Action.Path)));
    except
      { Non-executable actions do not have a Path property. }
      TaskPath := '';
    end;
    if CompareText(TaskPath, ExpandConstant('{app}\{#AppExe}')) = 0 then
      Result := True;
  end;
end;

procedure RemoveInstalledSchedules;
var
  Service, RootFolder, Tasks, Task: Variant;
  I: Integer;
begin
  Service := CreateOleObject('Schedule.Service');
  Service.Connect;
  RootFolder := Service.GetFolder('\');
  Tasks := RootFolder.GetTasks(1);
  for I := Tasks.Count downto 1 do
  begin
    Task := Tasks.Item(I);
    if TargetsThisInstallation(Task) then
    begin
      Log('Removing scheduled task for this installation: ' + String(Task.Name));
      RootFolder.DeleteTask(String(Task.Name), 0);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveInstalledSchedules;
end;
