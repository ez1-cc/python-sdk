from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ez1-python-sdk",
    version="1.0.0",
    author="ez1",
    description="Official Python SDK for EasyOne API with client-side encryption",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ez1-cc/python-sdk",
    project_urls={
        "Bug Reports": "https://github.com/ez1-cc/python-sdk/issues",
        "Source": "https://github.com/ez1-cc/python-sdk",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "cryptography>=41.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
        ],
    },
    keywords="ez1 file-upload encryption aes-gcm storage sdk",
)
