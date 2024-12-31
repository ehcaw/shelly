from setuptools import find_namespace_packages, setup, find_packages

setup(
    name='zap',
    version='0.1',
     py_modules=['splat'],
        install_requires=[
        'Click',
    ],
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        zap=zap:cli
    ''',
)
