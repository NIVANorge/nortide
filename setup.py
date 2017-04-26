"""A setuptools setup for module.

For more information on setuptools see:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='nortide',
    version='0.1',
    description='Python module for interfacing with the http://api.sehavniva.no/ API',
    long_description=long_description,
    url='https://github.com/NIVANorge/nortide',
    author='Grunde Løvoll',
    author_email='grunde.loevoll@niva.no',
    license='MIT',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: REST API Wrapper',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='waterlevel tide development marine',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    # py_modules=["nortide"],
    install_requires=['requests', 'pandas'],
    # entry_points={
    #     'console_scripts': [
    #         'nortide=nortide:main', # MUST implement this, also add test-script?
    #     ],
    # },
    test_suite='nortide_test',
)