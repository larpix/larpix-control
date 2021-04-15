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
        long_description_content_type='text/markdown',
        license='Other/Proprietary License',
        url='https://github.com/larpix/larpix-control',
        author='Peter Madigan and Sam Kohn',
        author_email='pmadigan@lbl.gov',
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Science/Research',
            'Programming Language :: Python :: 3'
        ],
        keywords='dune physics',
        packages=find_packages(),
        install_requires=[
            'pyserial ~=3.4',
            'pytest ~=6.2',
            'bitarray ~=0.8',
            'pyzmq ~= 18.0',
            'sphinx_rtd_theme ~= 0.5',
            'numpy ~= 1.16',
            'h5py ~= 3.1',
            'bidict ~= 0.18.0',
            'networkx ~= 2.2'
            ],
        scripts=[
            'scripts/gen_controller_config.py',
            'scripts/gen_hydra_simple.py',
            'scripts/convert_rawhdf5_to_hdf5.py',
            'scripts/packet_hdf5_tool.py',
            'scripts/raw_hdf5_tool.py'
            ],
        package_data={
            'larpix.configs': ['*/*.json'],
            },
)
