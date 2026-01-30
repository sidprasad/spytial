from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    with open(os.path.join(os.path.dirname(__file__), 'README.md'), 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name="spytial_diagramming",
    version="0.6.4",
    packages=find_packages(),
    install_requires=[
        "jinja2>=3.0.0",
        "pyyaml>=6.0",
        "ipython>=8.0.0",
    ],
    extras_require={
        "headless": ["selenium>=4.0.0"],
        "dev": [
            "pytest>=7.0.0",
            "flake8>=6.0.0", 
            "black>=23.0.0",
        ],
    },
    author="Siddhartha Prasad",
    author_email="", # Will be filled when available
    description="sPyTial: Spatial Python visualization with declarative constraints",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/sidprasad/spytial",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Education", 
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    license="MIT",
    keywords="visualization, diagrams, spatial, constraints, data-structures",
    project_urls={
        "Bug Reports": "https://github.com/sidprasad/spytial/issues",
        "Source": "https://github.com/sidprasad/spytial",
    },
    include_package_data=True,
)
