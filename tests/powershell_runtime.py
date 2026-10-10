"""Select the real PowerShell runtime without skipping executable contracts."""

import os
import shutil


def powershell_executable() -> str:
    name = "powershell" if os.name == "nt" else "pwsh"
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"{name} is required to execute the PowerShell contracts")
    return executable
