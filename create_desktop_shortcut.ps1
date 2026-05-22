$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target = Join-Path $scriptPath "Start_rni_app.bat"
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "Start RNI App.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $scriptPath
$shortcut.IconLocation = "$target,0"
# Ejecutar la aplicación con la ventana minimizada
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output "Acceso directo creado: $shortcutPath"
