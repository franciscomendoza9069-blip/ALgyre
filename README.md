<img src="static/icon.svg" width="52" alt="ALgyre logo">

# ALgyre

**Your company's environmental data, on your computer.**

[English](README.md) · [Castellano](README.es.md) · [Install](docs/guides/install.md) · [Screenshots](docs/gallery.md)

Created by Paco to solve a need in his own company: keep consumption records, evidence and emissions calculations together. Download it, choose a local password and start working. No signup or external ALgyre server required.

![ALgyre dashboard with fictional demonstration data](docs/images/dashboard.jpg)

*Real application, fictional data. The interface currently uses Spanish labels.*

## What it does

| Collect | Review | Report |
| --- | --- | --- |
| Enter activities, import Excel/CSV and attach PDFs. | Document emission factors, check gaps and track corrections. | See calculated emissions by scope and export PDF/CSV. |

13 activity categories across scopes 1, 2 and selected scope 3 activities. **You supply documented emission factors.** Missing factors stay pending. [Coverage and limitations →](docs/guides/methodology.es.md)

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
Invoke-WebRequest -Uri "https://github.com/franciscomendoza9069-blip/ALgyre/archive/refs/heads/main.zip" -OutFile "ALgyre.zip"
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
## Find your way

| I want to… | Open |
| --- | --- |
| Install or troubleshoot | [Installation](docs/guides/install.md) · [Castellano](docs/guides/install.es.md) |
| Learn the daily workflow | [Company guide, in Spanish](docs/guides/usage.es.md) |
| Browse screens | [Screenshot gallery](docs/gallery.md) |
| Understand the code | [Repository map](docs/README.md) · [Development](docs/technical/development.es.md) |

## License

Free for internal business operations under [PolyForm Internal Use 1.0.0](LICENSE). Internal modifications are permitted; redistribution, resale and offering it as a service to third parties are outside the license permissions.

© 2026 Paco · [Author](https://github.com/franciscomendoza9069-blip) · [Changes](CHANGELOG.md)

## How to Contribute

To contribute to my project, you can test it, report issues, and suggest improvements — all with the goal of improving the final product. To collaborate on the project, contact me via email: francisco.mendoza9069@gmail.com. I accept donations: https://www.paypal.com/paypalme/gymapp

