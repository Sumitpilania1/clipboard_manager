tell application "Terminal"
    do script "cd " & quoted form of POSIX path of ((path to me as text) & "::") & " && ./run_clipboard_manager.command"
    set custom title of front window to "Clipboard Manager V2"
    activate
end tell
