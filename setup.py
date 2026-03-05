from setuptools import setup, find_packages

setup(
    name="silabs-mlops-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "requests",
        "python-dotenv",
        "databricks-zerobus-ingest-sdk",
        "grpcio",
        "protobuf",
        "tensorflow",
        "PyYAML",
        # Add other dependencies here
    ],
    entry_points={
        "console_scripts": [
            "silabs-mlops=silabs_mlops.cli:main",
        ],
    },
)
