[Setup]
AppName=RadarView
AppVersion=1.2.0
DefaultDirName={pf}\RadarView
DefaultGroupName=RadarView
OutputDir=.\Output
OutputBaseFilename=RadarView_v1.2.0_Installer
Compression=lzma
SolidCompression=yes
LicenseFile=C:\Users\abbym\Documents\RadarView\LICENSE.txt
WizardImageFile=C:\Users\abbym\Documents\RadarView\Resources\installer\launch-background-end.bmp
WizardSmallImageFile=C:\Users\abbym\Documents\RadarView\Resources\installer\launch-background.bmp
SetupIconFile=C:\Users\abbym\Documents\RadarView\Resources\icon\icon.ico
WizardStyle=modern

[Files]
; Main Executable
Source: "dist\RadarMain.exe"; DestDir: "{app}"; Flags: ignoreversion

; External resources
Source: "resources\*"; DestDir: "{app}\resources"; Flags: recursesubdirs createallsubdirs
Source: "{app}"; DestDir: "{app}\"; Flags: recursesubdirs createallsubdirs

; Icon file
Source: "Resources\icon\icon.ico"; DestDir: "{app}\resources\icon"; Flags: ignoreversion

[Icons]
; Create a shortcut on the Desktop and Start Menu
Name: "{userdesktop}\RadarView"; Filename: "{app}\RadarMain.exe"; IconFilename: "{app}\Resources\icon\icon.ico"
Name: "{group}\RadarView"; Filename: "{app}\RadarMain.exe"; IconFilename: "{app}\Resources\icon\icon.ico"

; Uninstaller Shortcut
Name: "{group}\Uninstall RadarView"; Filename: "{uninstallexe}"

[Registry]
; Optional: Add entry to the registry for uninstallation
Root: HKCU; Subkey: "Software\RadarView"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"

[Run]
; Optional: Run the app after installation
Filename: "{app}\RadarMain.exe"; Description: "Launch RadarView"; Flags: nowait postinstall skipifsilent

[CustomMessages]
WelcomeLabel=Welcome to the RadarView Installer!
SelectComponentsLabel=Select the components you want to install.

[Code]
procedure InitializeWizard();
begin
  WizardForm.WelcomeLabel1.Caption := CustomMessage('WelcomeLabel');
  WizardForm.ComponentsList.Top := WizardForm.ComponentsList.Top + 10;
  WizardForm.ComponentsList.Font.Style := [fsBold];
end;

