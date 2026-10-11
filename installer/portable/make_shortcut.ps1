# Creates a "Signal Viewer" shortcut (with the app icon) on the desktop.
# Called by "Create desktop shortcut.bat". Paths are taken from where this folder is now:
# if the folder is moved later, run it again.
#
# Unicode-safe: desktops are often in OneDrive with a localized name ("OneDrive\שולחן העבודה").
# The old WScript.Shell shortcut object cannot save to such paths, so the shortcut is written
# through the Windows shell API (IShellLinkW, Unicode). If that is not allowed on this PC,
# the WScript object writes it under an English temp name and it is MOVED to the desktop.
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')        # also follows OneDrive-redirected desktops
if (-not $desktop) {                                      # unusual policies: fall back to the profile folder
    $profileDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    $desktop = Join-Path $profileDir 'Desktop'
}
if (-not (Test-Path -LiteralPath $desktop)) { throw "Desktop folder not found: $desktop" }

$lnk     = Join-Path $desktop 'Signal Viewer.lnk'
$target  = Join-Path $root 'runtime\pythonw.exe'
$arguments = '"' + (Join-Path $root 'app\run.py') + '"'
$icon    = Join-Path $root 'app\assets\icon.ico'

function New-LinkUnicode {
    if (-not ('SvShellLink' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
public class SvShellLinkCoClass {}

[ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
public interface ISvShellLinkW {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, int fFlags);
    void GetIDList(out IntPtr ppidl);
    void SetIDList(IntPtr pidl);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cch);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cch);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cch);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
    void GetHotkey(out short pwHotkey);
    void SetHotkey(short wHotkey);
    void GetShowCmd(out int piShowCmd);
    void SetShowCmd(int iShowCmd);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cch, out int piIcon);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, int dwReserved);
    void Resolve(IntPtr hwnd, int fFlags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
}

[ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("0000010b-0000-0000-C000-000000000046")]
public interface ISvPersistFile {
    void GetClassID(out Guid pClassID);
    [PreserveSig] int IsDirty();
    void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
    void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
    void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
    void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string ppszFileName);
}

public static class SvShellLink {
    public static void Create(string lnk, string target, string args, string dir, string icon, string desc) {
        ISvShellLinkW link = (ISvShellLinkW)new SvShellLinkCoClass();
        link.SetPath(target);
        link.SetArguments(args);
        link.SetWorkingDirectory(dir);
        link.SetIconLocation(icon, 0);
        link.SetDescription(desc);
        ((ISvPersistFile)link).Save(lnk, true);
    }
}
'@
    }
    [SvShellLink]::Create($lnk, $target, $arguments, $root, $icon, 'Signal Viewer')
}

function New-LinkViaTemp {
    # WScript writes to an English-named temp file; .NET then moves it (Unicode-safe).
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('SignalViewer-' + [Guid]::NewGuid().ToString('N') + '.lnk')
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($tmp)
    $s.TargetPath = $target; $s.Arguments = $arguments; $s.WorkingDirectory = $root
    $s.IconLocation = $icon + ',0'; $s.Description = 'Signal Viewer'
    $s.Save()
    Move-Item -LiteralPath $tmp -Destination $lnk -Force
}

try {
    New-LinkUnicode
} catch {
    Write-Output ('(Unicode shortcut API not available: ' + $_.Exception.Message + ' - using the fallback.)')
    New-LinkViaTemp
}
if (-not (Test-Path -LiteralPath $lnk)) { throw "The shortcut was not created: $lnk" }
Write-Output ('Shortcut created: ' + $lnk)
