<<<<<<< HEAD
from setuptools import setup, find_packages
=======
from setuptools import find_namespace_packages, setup, find_packages
>>>>>>> c5f2d769e12b962bd4de42d265ca9835737a304c

setup(
    name='shelly',
    version='0.1',
<<<<<<< HEAD
    packages=find_packages(),
    install_requires=[
        'click',
        'repopack',
        'setuptools',
        'virtualenv',
        'groq',
        'fastapi',
        'uvicorn',
        'prompt_toolkit',
        'requests',
        'black',
        'zmq',
        'langgraph',
        'langchain_openai',
        'langchain_ollama',
        'langchain_anthropic',
        'langchain_groq',
        'langchain',
        'langchain_community',
        'langchain-huggingface',
        'python-dotenv>=0.19.0',
        'textual-plotext',
        'textual',
        'pyte',
        'pyperclip',
        'shortuuid',
    ],
    entry_points={
        'console_scripts': [
            'shelly=my_app:main'
        ],
    },
=======
     py_modules=['shelly'],
        install_requires=[
        'Click',
    ],
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        shelly=shelly:cli
    ''',
>>>>>>> c5f2d769e12b962bd4de42d265ca9835737a304c
)
