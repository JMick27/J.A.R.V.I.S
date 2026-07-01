Set fso = CreateObject("Scripting.FileSystemObject")
basePath = fso.GetParentFolderName(WScript.ScriptFullName)
batchPath = fso.BuildPath(basePath, "Launch ATLAS.bat")
CreateObject("Wscript.Shell").Run Chr(34) & batchPath & Chr(34), 0, False
