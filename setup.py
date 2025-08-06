from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    with open(os.path.join(os.path.dirname(__file__), 'README.md'), 'r', encoding='utf-8') as f:
        return f.read()

# Read requirements from the main requirements.txt
def read_requirements():
    requirements = []
    req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(req_file):
        with open(req_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract just the package requirement, ignoring comments
                    requirement = line.split('#')[0].strip()
                    if requirement:
                        requirements.append(requirement)
    return requirements

setup(
    name="spytial",
    version="0.1.0",
    packages=find_packages(),
    install_requires=read_requirements(),
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
)
