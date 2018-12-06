# Lambdipy: Python packaging for Lambda

Lamdipy is a tool that allows packaging your python projects for the AWS Lambda environment.
A lot of the popular python packages (like scipy, numpy or tensorflow) are fairly oversized which makes them a pain
to fit into the AWS Lamda package.

Lambdipy aims to help with that by providing prebuilt popular packages that are know to be 
"problematic". 

## Installation
You can install lambdipy from pypi:
```
pip install lambdipy
```

## Usage

Build packages defined by your `requirements.txt` into a `./build` diretory:

```
lambdipy build
```

Build packages defined by your pipenv environment into a `./build` directory:

```
lambdipy build --from-pipenv
```

Build packages and also directly copy your scripts / modules into the `./build` directory:
```
lambdipy build -i your_script.py -i your_module
``` 

## Examples
//TODO
