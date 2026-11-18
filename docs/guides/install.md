# Install ALgyre on your computer

[English](install.md) · [Castellano](install.es.md) · [Project home](../../README.md)

No signup, email address or external ALgyre server is required. You will choose a password that protects the application on your computer.

## Windows: double-click setup

1. Download the project with **Code → Download ZIP** on GitHub.
2. Extract the ZIP into a writable folder. Do not run files from inside the ZIP.
3. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). Select **Add Python to PATH** during setup.
4. Double-click **Abrir ALgyre.cmd** in the extracted folder. The first start prepares the Python environment and downloads the required libraries.
5. In your browser, choose a local password of at least ten characters or select **Explorar con datos de ejemplo** to explore fictional data.

The Windows launcher opens **http://127.0.0.1:8765**. `127.0.0.1` refers to your own computer. Keep the application running while you work; close it using **Cerrar ALgyre.cmd**. Closing the browser tab alone does not stop the program.

The interface uses Spanish labels. Files in `scripts/` implement the launchers; you normally only need the two `.cmd` shortcuts in the main folder.

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
