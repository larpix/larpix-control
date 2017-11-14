'''
The setup.py file for larpix-control.

'''

from setuptools import setup, find_packages
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
        name='larpix-control',
        version='0.5.2',
        description='Control the LArPix chip',
        long_description=long_description,
        url='https://github.com/samkohn/larpix-control',
        author='Sam Kohn',
        author_email='skohn@lbl.gov',
        classifiers=[
            'Development Status :: 2 - Pre-Alpha',
            'Intended Audience :: Science/Research',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
        ],
        keywords='dune physics',
        packages=find_packages(),
        install_requires=['pyserial','bitstring','pytest'],
        scripts=['scripts/larpix-drivercheck-ubuntu',
                 'scripts/larpix-drivercheck-mac',
                 'scripts/larpix-find-device-ubuntu',
                 'scripts/larpix-find-device-mac'],
)
