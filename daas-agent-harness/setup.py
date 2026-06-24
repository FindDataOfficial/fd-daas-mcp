from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-daas",
    version="0.1.0",
    description="CLI for multi-source data access — AKShare, World Bank, CKAN, Chinese Statistics",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    install_requires=[
        "click>=8.0",
        "pandas>=1.0",
        "sqlalchemy>=1.4",
        "pyyaml>=6.0",
    ],
    extras_require={
        "repl": ["prompt_toolkit>=3.0"],
        "dev": ["pytest>=8.0"],
        "akshare": ["akshare>=1.17.0"],
        "worldbank": ["wbgapi>=1.1"],
        "ckan": ["ckanapi>=4.8"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-daas=cli_anything.daas.cli:cli",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
)
