#define MyAppName "YT to MP3 Converter"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Serge Chaanine"
#define MyAppExeName "YT to MP3 Converter.exe"
#ifndef RepositoryRoot
#define RepositoryRoot SourcePath + "..\"
#endif
#ifndef ApplicationDirectory
#define ApplicationDirectory RepositoryRoot + "dist\YT to MP3 Converter"
#endif
#ifndef InstallerOutputDirectory
#define InstallerOutputDirectory RepositoryRoot + "dist\installer"
#endif

[Setup]
AppId={{D551413F-EDEA-4706-B72A-13F0EBB8FF3E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#InstallerOutputDirectory}
OutputBaseFilename=YT-to-MP3-Converter-Setup-{#MyAppVersion}
SetupIconFile={#RepositoryRoot}assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#ApplicationDirectory}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
