# Windows installer with Inno Setup

This document describes how to turn a **PyInstaller** build of scrcpy-gui into a normal Windows **setup program** using [Inno Setup](https://jrsoftware.org/isinfo.php). Inno does not compile Python; it **packages** the `dist\scrcpy-gui\` folder (or a one-file exe) into an installer with shortcuts and uninstall support.

## Prerequisites

1. **Inno Setup 6** (or current supported version) installed on Windows. The command-line compiler is typically:

   `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

2. A **PyInstaller folder build** from the repository root (recommended for installers). See the [README](../README.md) section *Windows executable* and build `dist\scrcpy-gui\` with `scrcpy-gui.exe` and `_internal\` inside it.

## Why folder build + Inno

- **Folder build**: one directory to copy recursively; fast startup; fewer surprises than `--onefile`.
- **Inno**: single `setup.exe` you can send to others; installs under Program Files; Start menu entry; entry in Apps & features for uninstall.

## Sample Inno script (`.iss`)

Save as e.g. `scrcpy-gui.iss` in the **repository root** (same folder as `dist\` after you build), or adjust all paths below. Replace `AppId` with a **stable GUID** you generate once and keep for all releases of this product (upgrades rely on it).

```ini
#define MyAppName "scrcpy-gui"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "Your name or org"
#define MyAppExeName "scrcpy-gui.exe"
#define DistDir "dist\scrcpy-gui"

[Setup]
AppId={{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=scrcpy-gui-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
; Optional: branding (paths relative to this .iss file; use ..\ if the .iss lives in a subfolder)
SetupIconFile=logo_ico.ico
WizardImageFile=logo_bmp.bmp
; Optional: LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
```

Notes:

- **`[Files]`** must use `recursesubdirs` so `_internal\` and all DLLs are installed.
- **`ArchitecturesInstallIn64BitMode=x64`** matches a typical 64-bit PyInstaller build on Windows 10/11.
- **`{#DistDir}`** and icon paths assume the `.iss` file is in the **repo root**. If you put the script under e.g. `installer\`, prefix assets with `..\` (e.g. `SetupIconFile=..\logo_ico.ico`).

### Wizard images

- **`SetupIconFile`**: `.ico` for the setup program’s taskbar/title bar. This repo includes `logo_ico.ico` at the root for reuse.
- **`WizardImageFile`**: BMP shown on the wizard; Inno expects specific dimensions for the classic large image (commonly **164×314** pixels—confirm in [Inno Setup Help: WizardImageFile](https://jrsoftware.org/ishelp/topic_setup_wizardimagefile.htm) for your version). Resize `logo_bmp.bmp` if the wizard crops or looks wrong.

### Optional: `LicenseFile`, version info

Point `LicenseFile=` at `LICENSE` or a notice bundle. Keep `AppVersion` in sync with the version you ship in the app.

## Compile the installer

**GUI:** open the `.iss` in Inno Setup Compiler and choose Build.

**CLI** (adjust path to `ISCC.exe`):

```text
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" path\to\scrcpy-gui.iss
```

Output appears under `OutputDir` (e.g. `installer\scrcpy-gui-setup.exe`).

## Automation idea

1. Activate venv, `pip install -e ".[dev]"`.
2. Run PyInstaller (folder build, with `--icon` if desired—see README).
3. Run `ISCC.exe` on your `.iss`.

A small PowerShell or batch script at the repo root can chain steps 2–3.

## Sharing the installer

You can send the generated **setup `.exe`** to others; they run it once. They do **not** need Python installed.

**SmartScreen:** unsigned installers may show a warning until you **code-sign** the installer (and optionally the inner exe). Friends can use “More info” → “Run anyway” if they trust the source.

## Alternative: zip the PyInstaller folder

Without Inno, zip the entire **`dist\scrcpy-gui\`** folder; recipients extract and run `scrcpy-gui.exe`. No formal install or uninstall, but nothing extra to install on your machine beyond PyInstaller.

## One-file PyInstaller (`--onefile`)

You can point `[Files]` at a single `dist\scrcpy-gui.exe` instead of a directory, but folder mode is usually simpler for installers and starts faster.

## References

- [Inno Setup Documentation](https://jrsoftware.org/ishelp/)
- [PyInstaller manual](https://pyinstaller.org/en/stable/)
