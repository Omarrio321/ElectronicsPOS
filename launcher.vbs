' ============================================================
' launcher.vbs — ElectroPOS Silent Launcher
' Double-click this file (or use a Desktop shortcut pointing
' to it) to start the server with ZERO visible windows.
'
' Window style 0 = completely hidden
' False = do not wait for the process to finish
' ============================================================

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Build the full path to start_server.bat so it works from any
' working directory (e.g. when launched from a Desktop shortcut).
Dim scriptDir
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

WshShell.Run """" & scriptDir & "\start_server.bat""", 0, False

Set WshShell = Nothing
