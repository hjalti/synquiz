import os

from setuptools import setup

ROOT = os.path.abspath(os.path.dirname(__file__))

with open('README.md') as f:
    readme = f.read()

about = {}
with open(os.path.join(ROOT, 'synquiz', '__version__.py')) as f:
    exec(f.read(), about)

setup(
    name=about['__name__'],
    version=about['__version__'],
    description='An overly complex pubquiz generator',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/hjalti/synquiz',
    author=about['__author__'],
    author_email=about['__author_email__'],
    license=about['__version__'],
    packages=['synquiz'],
    package_data={'synquiz': ['data/*.html']},
    python_requires='>=3.6.0',
    install_requires=[
        'pyyaml',
        'mako',
        'watchdog',
        'filetype',
        'requests',
    ],
    entry_points={
        'console_scripts': [
            'synquiz=synquiz:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Games/Entertainment',
    ]
)
