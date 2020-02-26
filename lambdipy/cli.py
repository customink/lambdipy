import click
from . import __version__
import glob
import os
import sys


from docker.errors import BuildError


from .package_build import PackageBuild, build_package_build_dict
from .project_build import get_requirements_from_pipenv, parse_requirements, resolve_requirements
from .project_build import prepare_resolved_requirements, copy_prepared_releases_to_build_directory
from .project_build import install_non_resolved_requirements, copy_include_paths
from .project_build import NoReleaseCandidate, ReleaseRequirementsMissmatched
from .release import get_release, release as release_package


import warnings
warnings.filterwarnings("ignore")


@click.group()
def cli():
    """A tool for building and packaging python packages for AWS Lambda."""
    pass


@cli.command()
def version():
    print(__version__)


# TODO: allow configuration
#  - custom build folder
#  - override build recipes
#  - delete unneeded folders
#  - do not require docker for build - can strip before packaging
#  - allow setting whether to strip


@cli.command()
@click.option('--from-pipenv', '-p', is_flag=True, help='Build dependencies from Pipfile.lock')
@click.option('--dev', '-d', is_flag=True, help='If dependencies are built from Pipfile.lock, include development '
                                                'dependencies as well.')
@click.option('--include', '-i', multiple=True, help='Include these paths in the final build')
@click.option('--keep-tests', '-t', multiple=True, help='Exclude deletions of tests for these packages')
@click.option('--no-docker', '-x', is_flag=True, help='Do not use Docker for package build (lambdipy itself runs in '
                                                      'lambci/lambda:build-python{PYTHON_VERSION} container)')
def build(from_pipenv, dev, include, keep_tests, no_docker):
    if from_pipenv:
        requirements = parse_requirements(get_requirements_from_pipenv(dev))
    else:
        requirements = parse_requirements(open('requirements.txt').read())

    if os.environ.get('PYTHON_VERSION', False):
        python_version = os.environ.get('PYTHON_VERSION')
    else:
        python_version = f'{sys.version_info.major}.{sys.version_info.minor}'

    release_paths = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'releases/**/**/build*python{python_version}*json')
    package_builds = build_package_build_dict(glob.glob(release_paths))

    try:
        resolved_requirements = resolve_requirements(requirements, package_builds)
        package_paths = prepare_resolved_requirements(resolved_requirements)
        copy_prepared_releases_to_build_directory(package_paths)
        install_non_resolved_requirements(resolved_requirements, requirements, python_version, keep_tests, no_docker)
        copy_include_paths(include)
        print('Build done')

    except NoReleaseCandidate as e:
        print(f'{e.requirement.name} needs to be built but we couldn\'t find a release candidate for {e.requirement.specifiers}')
        available_versions = ', '.join(sorted(list(map(lambda x: x.package_version, package_builds[e.requirement.name]))))
        print(f'Available versions are: {available_versions}')
        print('If you believe this version should be available, please open an issue on GitHub')
    except ReleaseRequirementsMissmatched as e:
        print(f'{e.requirement.name} needs to be built but we couldn\'t find a release candidate for {e.requirement.specifiers}')
        print('We found the following candidates, but they have dependecies\nthat clash with your project requirements:')
        for candidate in e.potential_candidates:
            print(f'{candidate.git_tag()} {candidate.pypi_dependencies()}')
        print('If you believe this combination of requirements should be available, please open an issue on GitHub')
    except BuildError as e:
        print(e.msg)
        for log in e.build_log:
            if 'stream' in log:
                print(log['stream'], end='')


@cli.command()
@click.argument('package')
@click.option('--tag', '-t')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--release', '-r', is_flag=True)
def prepare(package, tag, verbose, release):
    release_paths = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases/**/**/build*.json')
    package_path = next((path for path in glob.glob(release_paths) if package in path and (tag is None or tag in path)), None)
    package_build = PackageBuild(package_path)
    print(f'Building {package_build}...')
    try:
        package_build.build_docker(verbose=verbose)
        package_build.copy_from_docker()
        print(f'Built {package_build} inside {package_build.build_directory()}')
        if release:
            print('Releasing...')
            release_package(package_build)
    except BuildError as e:
        print(e)
        for log in e.build_log:
            if 'stream' in log:
                print(log['stream'], end='')


@cli.command()
@click.option('--verbose', '-v', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--filter', '-f')
@click.option('--parallel-index')
@click.option('--parallel-total')
def release(verbose, dry_run, filter, parallel_index, parallel_total):
    release_paths = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases/**/**/build*.json')
    for i, path in enumerate(sorted(glob.glob(release_paths))):
        if filter is not None and filter not in path:
            continue

        if parallel_index is not None and parallel_total is not None and i % int(parallel_total) != int(parallel_index):
            continue

        package_build = PackageBuild(path)
        # print(open(path).read())
        # print(str(package_build))
        print(f'Checking whether {package_build} is released')
        if not get_release(package_build, use_token=True):
            try:
                print(f'{package_build} not released, building...')
                package_build.build_docker(verbose=verbose)
                package_build.copy_from_docker()
                print(f'Built {package_build} inside {package_build.build_directory()}')
                if not dry_run:
                    print('Releasing...')
                    release_package(package_build)
                else:
                    print('This is a dry run, not releasing...')
            except BuildError as e:
                print(e)
                for log in e.build_log:
                    if 'stream' in log:
                        print(log['stream'], end='')
        else:
            print(f'{package_build} already released, skipping...')

if __name__ == '__main__':
    cli()
