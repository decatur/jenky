"""
"""
from setuptools import setup

package_data = {'': ['*'], 'jenky': ['html/*']}

dist = setup(
    name='jenky',
    version='0.2.0',
    author="Wolfgang Kühn",
    description="A build and deploy server for Python developers",
    packages=['jenky'],
    install_requires=['aiofiles', 'fastapi', 'psutil', 'uvicorn'],
    extras_require={},
    package_data=package_data
)
