"""
"""
from setuptools import setup

dist = setup(
    name='jenky',
    version='0.0.1',
    author="Wolfgang Kühn",
    description=("A build and deploy server for Python developers"),
    packages=['jenky'],
    include_package_data=True,
    install_requires=['aiofiles', 'fastapi', 'psutil', 'uvicorn'],
    extras_require={}
)
