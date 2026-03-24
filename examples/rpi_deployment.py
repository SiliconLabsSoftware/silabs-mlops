"""
Raspberry Pi Deployment Example - SiLabs MLOps
----------------------------------------------
This script demonstrates how to use the 'RPiDeployer' to:
1. Transfer a local firmware or model file to a remote Raspberry Pi via SCP.
2. Flash it to a target Silicon Labs device connected to that Pi via SSH 
   and Simplicity Commander.
"""
import os
import logging
from dotenv import load_dotenv

# Suppress TensorFlow oneDNN floating-point warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Load .env credentials if necessary
load_dotenv()

from silabs_mlops.model.deployer import RPiDeployer

def run_example():
    print("\n--- SiLabs MLOps RPi Deployment ---")
    
    # Path to your local firmware file (e.g., an .s37 or .bin file)
    # Using the example file found in the directory
    local_file = "examples/bt_soc_thermometer_freertos.s37"
    
    # The IP address or hostname of your Raspberry Pi
    # Replace this with your actual Raspberry Pi IP Address
    rpi_host = "192.168.1.111" 
    
    # The SSH user for the Raspberry Pi
    rpi_user = "aimlraspberry"
    
    print(f"  Local File : {local_file}")
    print(f"  RPi Host   : {rpi_host} (User: {rpi_user})\n")

    # CONFIGURE RPI DEPLOYMENT
    try:
        deployer = RPiDeployer(
            rpi_host=rpi_host,
            rpi_user=rpi_user,
            local_file_path=local_file,
            # Path to Simplicity Commander on the Raspberry Pi. 
            # Assumes it is available in the rpi system PATH if "commander"
            commander_path="/home/aimlraspberry/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli" 
        )

        # Check if the file exists locally before running
        if not os.path.exists(local_file):
            print(f"Warning: Local file '{local_file}' not found.")
            print("Please create or specify a valid file path to run the actual deployment.")
            print("Skipping actual deployment step.")
            return

        print(f"Starting deployment to {rpi_host}...")
        deployer.deploy()
        print("\nDeployment via Raspberry Pi completed successfully.")
        
    except Exception as e:
        print(f"\nDeployment failed: {e}")

if __name__ == "__main__":
    run_example()
