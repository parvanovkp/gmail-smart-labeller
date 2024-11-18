from setuptools import setup, find_packages

setup(
    name="gmail-smart-labeler",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
        'openai',
        'google-api-python-client',
        'google-auth-oauthlib',
        'python-dotenv',
        'PyYAML',
        'tqdm'
    ],
    entry_points={
        'console_scripts': [
            'gmail-smart-label=smart_labeler.cli:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool for smart Gmail label management",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gmail-smart-labeler",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)