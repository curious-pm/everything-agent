!define AUTOSTART_ENTRY "Everything Agent"

!macro NSIS_HOOK_POSTUNINSTALL
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${AUTOSTART_ENTRY}"
!macroend
