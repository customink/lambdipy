"""
A tool for building and packaging python packages for AWS Lambda.
"""
from setuptools import find_packages, setup
from lambdipy import __version__ as version

dependencies = ['click', 'pygithub', 'docker', 'requirementslib', 'pipenv', 'tqdm']

setup(
    name='lambdipy',
    version=version,
    url='https://github.com/customink/lambdipy',
    license='BSD',
    author='Andrej Hoos',
    author_email='andrej.hoos@gmail.com',
    description='A tool for building and packaging python packages for AWS Lambda.',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'lambdipy = lambdipy.cli:cli',
        ],
    },
    package_data={
        'lambdipy': [
            'releases/**/**/*.json'
        ]
    },
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        # 'Development Status :: 1 - Planning',
        'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
