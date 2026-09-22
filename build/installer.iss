; Instalador de Spamed Travel (Inno Setup 6).
;
; Se compila solo, desde build\build.bat, DESPUES de que PyInstaller dejo
; dist\SpamedTravel\. A mano:
;
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
;
; No pide permisos de administrador: instala en la carpeta del usuario. Por
; eso el desinstalador tampoco toca %LOCALAPPDATA%\SpamedTravel\, donde viven
; la base y los backups (ver el bloque [Code] al final).

#define MiNombre     "Spamed Travel"
#define MiVersion    "1.1.0"
#define MiAppId      "SpamedTravel"
#define MiEditor     "Spamed Travel"
#define MiEjecutable "SpamedTravel.exe"

[Setup]
; Este GUID identifica a la app para actualizaciones y desinstalacion.
; NO cambiarlo entre versiones: si cambia, Windows trata a la version nueva
; como un programa distinto y quedan las dos instaladas a la vez.
AppId={{29DEDEC8-EA63-4042-B4D0-000C4FF248E7}
AppName={#MiNombre}
AppVersion={#MiVersion}
AppVerName={#MiNombre} {#MiVersion}
AppPublisher={#MiEditor}
DefaultDirName={localappdata}\Programs\{#MiAppId}
DefaultGroupName={#MiNombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\instalador
OutputBaseFilename=SpamedTravel_Setup_{#MiVersion}
SetupIconFile=..\src\spamed\recursos\spamed.ico
UninstallDisplayIcon={app}\{#MiEjecutable}
UninstallDisplayName={#MiNombre} {#MiVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; La app es de 64 bits (PySide6 x64); en un Windows de 32 no arranca.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Todo lo que dejo PyInstaller, incluido _internal\ (Qt, Chromium, recursos).
Source: "..\dist\SpamedTravel\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MiNombre}"; Filename: "{app}\{#MiEjecutable}"
Name: "{group}\Desinstalar {#MiNombre}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MiNombre}"; Filename: "{app}\{#MiEjecutable}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MiEjecutable}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MiNombre, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[Code]
// Desinstalar no borra la base de datos ni los backups: viven fuera de
// {app}. Se avisa donde quedaron por si el usuario los quiere conservar o
// borrar a mano.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Carpeta: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Carpeta := ExpandConstant('{localappdata}\{#MiAppId}');
    if DirExists(Carpeta) then
      MsgBox('Se desinstalo {#MiNombre}.' + #13#10#13#10 +
             'Tus datos NO se borraron. La base y las copias de seguridad ' +
             'quedaron en:' + #13#10#13#10 + Carpeta + #13#10#13#10 +
             'Si no los vas a necesitar mas, podes borrar esa carpeta a mano.',
             mbInformation, MB_OK);
  end;
end;
