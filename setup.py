import setuptools

setuptools.setup(
    name = 'inoti_make',
    description='Make-like file to watch directories and run commands when events happen',
    version = '1.0.0',
    packages = setuptools.find_packages(),
    scripts=['bin/inoti-make']
)
