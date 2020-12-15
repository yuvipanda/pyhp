from setuptools import find_packages, setup

# Imports __version__, reference: https://stackoverflow.com/a/24517154/2220152

setup(
    name='pyhp-hypertext-preprocessor',
    version='0.1',
    url='https://github.com/yuvipanda/pyhp',
    license='3-clause BSD',
    author='YuviPanda',
    author_email='yuvipanda@gmail.com',
    description='Python Hyptertext Preprocessor - like PHP, but for Python',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=['jinja2', 'flask'],
    zip_safe=False,
)
