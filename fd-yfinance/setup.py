from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-yfinance",
    version="0.1.0",
    description="CLI for yfinance global / Yahoo Finance market data library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/ranaroussi/yfinance",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    install_requires=[
        "click>=8.0",
        "pandas>=1.0",
        "yfinance>=0.2.0",
        "sqlalchemy>=1.4",
    ],
    extras_require={
        "repl": ["prompt_toolkit>=3.0"],
        "dev": ["pytest>=8.0"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-yfinance=cli_anything.yfinance.yfinance_cli:cli",
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
