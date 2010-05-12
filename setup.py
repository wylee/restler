from setuptools import setup, find_packages


version = '0.6.0'


setup(
    name='Restler',
    version=version,
    description="""RESTful base controller for Pylons 1.0.""",
    long_description="""\
Restler is a controller for Pylons projects that provides a set of default
RESTful actions that can be overridden as needed.

The Restler project is hosted at Google Code. Please see
http://code.google.com/p/restler/ for more details, documentation, etc.

Restler was originally extracted from the byCycle bicycle trip planner
(http://bycycle.org).

""",
    license='BSD/MIT',
    author='Wyatt L Baldwin',
    author_email='self@wyattbaldwin.com',
    keywords='web pylons controller REST WSGI',
    url='http://code.google.com/p/restler/',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Pylons',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
    ],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=(
        'decorator>=3.1.2',
        'SQLAlchemy>=0.6.0',
    ),
    test_suite = 'nose.collector',
)

