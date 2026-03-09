"""

setup.py
========

Packaging configuration for the silabs-mlops-cli.

Defines package metadata, dependencies, and the console entry point
for the `silabs-mlops` command-line tool.
"""

from setuptools import setup, find_packages

setup(
    name="silabs-mlops-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "requests",
        "python-dotenv",
        "PyYAML",
        "databricks-zerobus-ingest-sdk>=0.2.0",
        "grpcio",
        "protobuf",
        "mlflow",
        "tensorflow",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "silabs-mlops=silabs_mlops.cli:main",
        ],
    },
)
