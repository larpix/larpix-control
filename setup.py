'''
The setup.py file for larpix-control.

'''

from setuptools import setup, find_packages
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(os.path.join(here, 'VERSION')) as f:
    version = f.read()

setup(
        name='larpix-control',
        version=version,
        description='Control the LArPix chip',
        long_description=long_description,
        long_description_content_type="text/markdown",
        url='https://github.com/larpix/larpix-control',
        author='Peter Madigan and Sam Kohn',
        author_email='pmadigan@lbl.gov',
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Science/Research',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 2'
        ],
        keywords='dune physics',
        packages=find_packages(),
        install_requires=[
            'pyserial ~=3.4',
            'pytest ~=4.2',
            'larpix-geometry ==0.3.0',
            'bitarray ~=0.8',
            'pyzmq ~= 16.0',
            'sphinx_rtd_theme ~= 0.4.2',
            'numpy ~= 1.16',
            'h5py ~= 2.9',
            'bidict ~= 0.18.0'
            ],
        scripts=[
            'scripts/gen_controller_config.py'
            ],
        package_data={
            'larpix.configs.chip': 'configs/chip/*.json',
            'larpix.configs.controller': 'configs/controller/*.json',
            'larpix.configs.io': 'configs/io/*.json'
            },
)
