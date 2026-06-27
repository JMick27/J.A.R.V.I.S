Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
basePath = fso.GetParentFolderName(WScript.ScriptFullName)
batchPath = fso.BuildPath(basePath, "Launch JARVIS.bat")
shell.Run """" & batchPath & """", 0, False
