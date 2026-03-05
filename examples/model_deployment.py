"""
Model Deployment Example - SiLabs MLOps
--------------------------------------
This script demonstrates how to use the 'ModelDeployer' to:
1. Download a model from a Databricks Volume (via registry name).
2. Flash it to a target device via Simplicity Commander.
"""
import os
import sys

# Suppress TensorFlow oneDNN floating-point warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import logging
from dotenv import load_dotenv

# Load .env credentials before imports
load_dotenv()

from silabs_mlops.model import ModelDeployer, DeployConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_example():
    print("\n--- SiLabs MLOps Deployment ---")
    print("  Model  : iot_model")
    print("  Device : 192.168.1.100\n")

    # 2. CONFIGURE DEPLOYMENT
    # - model_uri can be a registry name, Volume URL, MLflow URI (models:/...), or Local Path.
    config = DeployConfig(
        model_uri="iot_model",
        device_ip="192.168.1.100",
        # commander_path is optional (will be auto-discovered if not provided)
        commander_path=r"C:\Users\ANMOYADA\Downloads\SimplicityCommander-Windows\SimplicityCommander-Windows\CommanderCLI\Simplicity Commander CLI\commander-cli.exe",
        verify=True
    )

    try:
        deployer = ModelDeployer(config)
        deployer.deploy()
        print("\nDeployment completed successfully.")
    except Exception as e:
        print(f"\nDeployment failed: {e}")

if __name__ == "__main__":
    run_example()
