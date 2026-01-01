"""
Setup script for Signal Viewer Pro
Professional signal visualization and analysis tool
"""

from setuptools import setup, find_packages
import os

# Read the long description from README
def read_long_description():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# Read requirements
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name='signal-viewer-pro',
    version='3.0.0',
    author='Signal Viewer Team',
    author_email='your.email@example.com',
    description='Professional signal visualization and analysis tool for time-series data',
    long_description=read_long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/signal-viewer-pro',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    py_modules=[
        'app',
        'data_manager',
        'signal_operations',
        'linking_manager',
        'config',
        'helpers',
        'callback_helpers',
        'flexible_csv_loader',
        'runtime_hook'
    ],
    include_package_data=True,
    package_data={
        '': [
            'assets/*.css',
            'assets/*.js',
            'assets/*.min.css',
            'assets/*.min.js',
        ],
    },
    install_requires=read_requirements(),
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'black>=22.0.0',
            'flake8>=4.0.0',
            'mypy>=0.950',
        ],
    },
    entry_points={
        'console_scripts': [
            'signal-viewer=app:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Visualization',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
        'Environment :: Web Environment',
    ],
    python_requires='>=3.8',
    keywords='signal visualization analysis time-series plotting data-science',
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/signal-viewer-pro/issues',
        'Source': 'https://github.com/yourusername/signal-viewer-pro',
        'Documentation': 'https://github.com/yourusername/signal-viewer-pro/wiki',
    },
)
