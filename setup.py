from setuptools import find_namespace_packages, setup, find_packages

setup(
    name='shelly',
    version='0.1',
     py_modules=['shelly'],
        install_requires=[
        'Click',
    ],
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        shelly=shelly:cli
    ''',
)
