from setuptools import find_namespace_packages, setup, find_packages


setup(
    name='shelly',
    version='0.1',
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
    }
)
