# Lambdipy: Python packaging for Lambda

Lamdipy is a tool that allows packaging your python projects for the AWS Lambda environment.
A lot of the popular python packages (like scipy, numpy or tensorflow) are fairly oversized which makes them a pain
to fit into the AWS Lamda bundle.

Lambdipy aims to help with that by providing prebuilt popular packages that are know to be 
oversized or otherwise difficult to deploy. 

## Installation
You can install lambdipy from pypi:
```
pip install lambdipy
```

## Supported environments
Python 2.7, 3.6 and 3.7 are all currently supported Lambda environments.

## Features
 * Automatically identify project requirements from your `requirements.txt` or pipenv environment
 * Provide pre-built popular packages for the AWS Lambda environment in order to speed up your builds
 * Automatically strips package binaries in order to make them as lean as possible
 * [TODO] Provide tips and recipes on how to further improve your bundle size
 
### What lambdipy isn't
 * Lambdipy is not a deployment tool, for that you will have to look at something like 
   https://github.com/serverless/serverless or https://github.com/awslabs/serverless-application-model
 * Lambdipy is not a package manager. It can retrieve pre-built packages from our own GitHub releases, 
   but do not expect any complicated requirement resolution capabilities. 

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
