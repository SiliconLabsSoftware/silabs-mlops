# Raspberry Pi Deployment Guide (SiLabs MLOps)

This guide documents the procedures for environment setup and model deployment via remote Raspberry Pi.

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
silabs-mlops-cli model deploy \
  --uri ./bt_soc_thermometer_freertos.s37 \
  --rpi-host 192.168.1.111 \
  --rpi-user aimlraspberry \
  --commander "/home/aimlraspberry/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"
```

### Via Python Script
Run the provided example in `examples/rpi_deployment.py`:
1. Open the script and verify the configuration.
2. Run from your project directory:
   ```bash
   python examples/rpi_deployment.py
   ```

### Via Jupyter Notebook
For an interactive experience, use the provided notebook:
1. Open `examples/rpi_deployment.ipynb` using Jupyter Notebook or VS Code.
2. Follow the cell-by-cell execution to flash your firmware.

---

## 4. Connectivity Troubleshooting

### Latency and Stability
If deployment fails with an SSH timeout:
1. **Verify Network Integrity**:
   ```bash
   ping <RPI_IP>
   ```
   *Expected: < 50ms latency, 0% packet loss.*
2. **Handle Poor Connections**:
   The `RPiDeployer` includes high-resilience settings (30s timeout, 5 retries) to mitigate issues on unstable Wi-Fi networks.

### Tool Discovery
Ensure the `commander_path` provided in the script or CLI matches the absolute path to the binary on the Raspberry Pi filesystem.
