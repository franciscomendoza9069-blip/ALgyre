# Install ALgyre on your computer

## Start in three steps

These instructions are for a first installation on **Windows**. You need an Internet connection during setup.

### 1. Install Python

Open the Windows Start menu, type **PowerShell** and open it. Copy and paste this command, then press **Enter**:

```powershell
winget install --id Python.Python.3.14 --exact --source winget --scope user
```

This downloads and installs Python and adds it to PATH, allowing Windows to find it when ALgyre starts. Follow any installation prompts.

**Once the installation finishes, close PowerShell and open a new window.** Then check:

```powershell
python --version
```

You should see **Python 3.14.x**.

> If Windows does not recognise `winget`, install or update **App Installer** from the Microsoft Store, then reopen PowerShell.

### 2. Download ALgyre

In the new PowerShell window, run these commands one at a time:

```powershell
Set-Location $HOME
```

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/franciscomendoza9069-blip/ALgyre/archive/refs/heads/main.zip" -OutFile "ALgyre.zip"
```

```powershell
Expand-Archive -LiteralPath ".\ALgyre.zip" -DestinationPath "."
```

```powershell
Set-Location ".\ALgyre-main"
```

These commands download the project, extract it into an **ALgyre-main** folder inside your Windows user folder, and open that folder in the terminal.

> If an `ALgyre-main` folder already exists, use a different empty folder for this installation. Back up any existing ALgyre data before updating.

### 3. Open ALgyre

Run:

```powershell
& ".\Abrir ALgyre.cmd"
```

The first launch prepares the application and downloads its required libraries. This may take a few minutes. ALgyre will then open in your browser.

Choose a local password or select **“Explorar con datos de ejemplo”** to explore fictional demonstration data. No registration or email address is required.

Your records and documents stay in the `data/` folder inside your installation. For future visits, double-click **Abrir ALgyre.cmd**. To stop the application, use **Cerrar ALgyre.cmd**.
## Manual setup

Open a terminal in the extracted project folder.

### Windows PowerShell

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe app.py
```

### Linux and macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python app.py
```

On Debian, install `python3-venv` with your package manager if the environment command reports that support is missing. Windows and Linux are checked by the repository's automated tests; macOS has not been separately verified.

Open **http://127.0.0.1:8765**. Keep the terminal open while working; press **Ctrl+C** to stop the program. You do not need an `.env` file for local mode.

## Data, updates and another computer

- The initial dependency installation needs Internet. Local use works without an external ALgyre service once the dependencies are installed.
- Records and documents are stored in `data/`. The real workspace and the demonstration use separate databases.
- Download a backup ZIP from **Configuración** before updating or moving to another computer. Keep it private and store a copy outside the application folder.
- On the destination, install the new copy, choose its local password and restore the ZIP from **Configuración**. Inventory and documents are restored; the previous password is not transferred.
- Save the local password in your password manager. Local mode does not send recovery emails.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Python is not found | Reopen your terminal after installing Python and check that it is on PATH. |
| The page does not open | Start the program first. In Windows, inspect `data/server-error.log`; in manual mode, read the terminal message. |
| A package is missing | Run the dependency installation command with the Python inside `.venv`. |
| The port is busy | Stop the other application using port 8765 before starting this copy. |
| I see a blank inventory | Your installation is independent. Restore your own backup if you are moving data. |

For an optional shared installation, your company can use [its own Debian server](../../deploy/LEEME.md). It is separate from this local setup.
