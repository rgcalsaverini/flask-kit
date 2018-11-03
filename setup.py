from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='flask-kit',
    version='0.0.1',
    url='https://gitlab.com/rgcalsaverini/flask-kit',
    author='Rui Calsaverini',
    author_email='rui.calsaverini',
    description='Utils for flask apps',
    packages=find_packages(),
    install_requires=required,
)
