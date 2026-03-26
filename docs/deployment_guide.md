# Raspberry Pi Deployment Guide (Silicon-Labs-MLOps-CLI)

This guide documents the procedures for environment setup and model deployment via remote Raspberry Pi.

---

## 0. Installation

Depending on your role, there are two ways to install this CLI:

### For End Users
If you are just using the SDK to deploy models, install the core dependencies only. Test files and testing tools are deliberately excluded to keep the installation lightweight.
```bash
pip install .
```

### For Developers
If you are modifying the code or running tests, you must include the `[test]` flag. This installs the core dependencies along with testing tools like `pytest` and `pytest-cov`. *(Note: The quotes are required on Windows).*
```bash
pip install -e ".[test]"
```

---

## 1. SSH Configuration (Passwordless Login)

To enable automated deployment without manual password entry, configure SSH key-based authentication using modern cryptography standards (Ed25519).

### A. Generate Ed25519 Keys
1. Open a terminal (PowerShell or Bash) on your local workstation.
2. Execute the key generation command:
   ```bash
   ssh-keygen -t ed25519
   ```
3. Follow the prompts to save the key (default path: `~/.ssh/id_ed25519`).
4. **Leave the passphrase empty** to ensure fully automated script execution.

### B. Retrieve Public Key
Display your public key to copy it:
```bash
cat ~/.ssh/id_ed25519.pub
```
The output will resemble: `ssh-ed25519 AAAAC3N... <user@hostname>`

### C. Install Key on Raspberry Pi
1. Connect to your Raspberry Pi via SSH:
   ```bash
   ssh <USER_NAME>@<RPI_IP_ADDRESS>
   ```
2. Initialize the SSH directory and set secure permissions:
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   ```
3. Append your public key to the authorized keys file:
   ```bash
   echo "<YOUR_PUBLIC_KEY_STRING>" >> ~/.ssh/authorized_keys
   ```
4. Set permissions for the authorized keys file:
   ```bash
   chmod 600 ~/.ssh/authorized_keys
   ```

---

## 2. Remote Toolchain Setup

### A. Simplicity Commander Installation
The `RPiDeployer` requires Simplicity Commander for Linux to be present on the target Pi.
- **Recommended Path**: `/home/<USER_NAME>/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli`

### B. Hardware Access (Udev Rules)
To allow flashing over USB without root privileges:
1. Create a new rules file:
   ```bash
   sudo nano /etc/udev/rules.d/99-jlink.rules
   ```
2. Insert the following configuration:
   ```text
   SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="0666", GROUP="plugdev"
   ```
3. Apply the changes:
   ```bash
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
4. **Final Sync**: 
   To ensure the rules are fully active, it is highly recommended to **reboot the Raspberry Pi** and then **physically disconnect and reconnect the Silicon Labs board** from the USB port.

---

## 3. Execution

### Via CLI
Run the following command from your terminal:
```bash
sml ops deploy \
  --uri ./model_path.s37 \
  --rpi-host <RPI_IP_ADDRESS> \
  --rpi-user <USER_NAME> \
  --commander "/home/<USER_NAME>/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"
```

### Via Python Script
Run the provided example in `examples/rpi_deployment.py`:
1. Open the script and verify the configuration.
2. Run from your project directory:
   ```bash
   python examples/rpi_deployment.py
   ```
---

## 4. Connectivity Troubleshooting

### Latency and Stability
If deployment fails with an SSH timeout:
1. **Verify Network Integrity**:
   ```bash
   ping <RPI_IP_ADDRESS>
   ```
   *Expected: < 50ms latency, 0% packet loss.*
2. **Handle Poor Connections**:
   The `RPiDeployer` includes high-resilience settings (30s timeout, 5 retries) to mitigate issues on unstable Wi-Fi networks.

### Tool Discovery
Ensure the `commander_path` provided in the script or CLI matches the absolute path to the binary on the Raspberry Pi filesystem.
