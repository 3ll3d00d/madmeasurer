import sys
from setuptools import setup, find_packages

majv = 0
minv = 8

if sys.version_info < (3,):
    print("This library is only tested with Python 3.7")
    sys.exit(1)

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='madmeasurer',
    version='%d.%d' % (majv, minv),
    description='Runs madMeasureHDR.exe against a variety of local content',
    long_description=readme,
    author='3ll3d00d',
    author_email='mattkhan@gmail.com',
    url="https://github.com/3ll3d00d/madmeasurer",
    packages=find_packages(exclude=('tests', 'docs')),
    license=license,
    classifiers=[
        'Programming Language :: Python :: 3.7'
    ],
    entry_points={
        'console_scripts': [
            'madmeasurer = madmeasurer.__main__:main'
        ]
    }
)
