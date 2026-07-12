from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-akshare",
    version="0.1.0",
    description="CLI for AKShare Chinese financial data library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/akfamily/akshare",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    install_requires=[
        "click>=8.0",
        "pandas>=1.0",
        "akshare>=1.17.0",
        "sqlalchemy>=1.4",
    ],
    extras_require={
        "repl": ["prompt_toolkit>=3.0"],
        "dev": ["pytest>=8.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-akshare=cli_anything.akshare.akshare_cli:cli",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
)
