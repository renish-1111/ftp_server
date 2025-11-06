# Simple FTP Server (pyftpdlib)

This repository contains a small, single-file FTP server built on top of `pyftpdlib`. It supports an interactive menu mode and a headless (non-interactive) mode driven by environment variables. This guide shows how to set it up on Windows and connect from Android/iOS devices on the same LAN.

## 0) Prerequisites

* **Python 3.x** must be installed on your system.
* **pip** (the Python package manager) must be available.

You can download Python from [python.org](https://www.python.org/).

## 1) Clone repository and install requirements

Clone the repository (or copy the folder to your machine) and install dependencies. In PowerShell:

```powershell
# clone (replace <repo-url> with your repository URL) or copy files
git clone https://github.com/renish-1111/ftp_server
cd ftp_server

python -m pip install -r requirements.txt
```

If you don't have Git, you can also download the repository ZIP and extract it.

## 2) Add the project folder to your PATH in Windows

Adding the folder containing `ftp_server.bat` to your system's `PATH` allows you to run the server from any directory in your terminal, simply by typing `ftp_server`.


### Method 1: Using PowerShell (Recommended)

This is a fast, one-line command to permanently add the folder to your `PATH`.

1.  Open a **PowerShell** terminal (not CMD).
2.  Run the following command. **Remember to replace `C:\Path\To\your\repo`** with the actual, full path to your project's folder.

    ```powershell
    [Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\Path\To\your\repo', 'Machine')
    ```

3.  You must **close and reopen** your terminal for the change to take effect.

---

### Method 2: Using System Properties (GUI)

You can also add the path manually through the Windows settings menu.

1.  Press the **Windows key** (or click the Start Menu) and type **`env`**.
2.  Select **"Edit the system environment variables"** from the search results.
3.  A "System Properties" window will open. Click the **"Environment Variables..."** button.
4.  In the top box ("System Variable"), find and select the variable named **`Path`**.
5.  Click the **"Edit..."** button.
6.  A new window will open. Click **"New"** on the right-hand side.
7.  Paste in the full path to your folder (e.g., `C:\Path\To\your\repo`).
8.  Click **"OK"** on all the windows to close and save your changes.



> **Important:** After using either method, you must **close and reopen any active Command Prompt or PowerShell terminals** for the `PATH` changes to apply.

## 3) Run the server

To start the server, open a command prompt or terminal.

Execute the following command:

```powershell
ftp_server
```

By default, the server will start and share the current directory (the folder where you ran the command).

Your server is now running. You can also customize key settings such as the port, username, password, or specify a different path to share.

## 4) Configure Android and iOS Clients

To access your files from a mobile device, you will need to use an FTP client app. Ensure your mobile device is connected to the **same Wi-Fi network** as the computer running the server.

> All the connection details you need (like the **IP Address**, **Port**, **Username**, and **Password**) are displayed in the terminal right after you start the server.
>
> If you need to see this information again, simply **select option 6** in the server menu.

---

### 📱 On Android

1.  Open the **Google Play Store** and download an FTP client (e.g., "FileZilla Client", "AndFTP") or use a file manager that supports FTP connections.
2.  Open the app and find the option to create a **new connection**.
3.  Enter the server details provided in your terminal:
    * **Host/Server:** Your computer's Local IP Address.
    * **Port:** The port your server is running on.
    * **Username:** The username you configured.
    * **Password:** The password you configured.
4.  Connect to the server to browse your files.

### 🍎 On iOS (iPhone/iPad)

1.  Open the **Apple App Store** and download an FTP client app (e.g., "FTPManager", "Documents by Readdle").
2.  In the app, find the option to add a **new connection** or server.
3.  Enter the same server details from your terminal:
    * **Host/Server:** Your computer's Local IP Address.
    * **Port:** The server's port.
    * **Username:** Your configured username.
    * **Password:** Your configured password.
4.  Save the connection and tap it to access your files.

