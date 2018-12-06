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

### Usage notes:
 * The build process currently requires docker.
   This will most likely change in the future.
 * The prebuilt packages are downloaded from GitHub using its API. If you see a rate limit error 
 (which you will definitely see on shared build environments like Travis, you can specify a
 `GITHUB_TOKEN` environmental variable containing a token generated at https://github.com/settings/tokens - 
 only the "Access public repositories" scope is needed) 

## Examples
//TODO
