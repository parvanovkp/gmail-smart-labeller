from setuptools import setup, find_packages

setup(
    name="gmail-smart-labeler",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.0.0',
        'openai>=1.0.0',
        'google-api-python-client>=2.0.0',
        'google-auth-oauthlib>=1.0.0',
        'python-dotenv>=0.19.0',
        'PyYAML>=6.0.0',
        'tqdm>=4.65.0',
        'colorama>=0.4.6'  # For cross-platform colored terminal output
    ],
    entry_points={
        'console_scripts': [
            'gmail-smart-label=smart_labeler.cli:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool for smart Gmail label management using AI",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gmail-smart-labeler",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Communications :: Email",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires='>=3.8',
    package_data={
        'smart_labeler': [
            'config/*.yaml',
            'config/*.json',
        ],
    },
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/gmail-smart-labeler/issues',
        'Source': 'https://github.com/yourusername/gmail-smart-labeler',
    },
    keywords='gmail email labels ai organization automation openai',
)