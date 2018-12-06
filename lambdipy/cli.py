import click
from . import __version__
import glob
import os

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
@click.option('--include', '-i', multiple=True, help='Include these paths in the final build')
def build(from_pipenv, include):
    if from_pipenv:
        requirements = parse_requirements(get_requirements_from_pipenv())
    else:
        requirements = parse_requirements(open('requirements.txt').read())

    release_paths = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases/**/**/build*.json')
    package_builds = build_package_build_dict(glob.glob(release_paths))

    try:
        resolved_requirements = resolve_requirements(requirements, package_builds)
        package_paths = prepare_resolved_requirements(resolved_requirements)
        copy_prepared_releases_to_build_directory(package_paths)
        install_non_resolved_requirements(resolved_requirements, requirements)
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


@cli.command()
def release():
    release_paths = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases/**/**/build*.json')
    for path in glob.glob(release_paths):
        package_build = PackageBuild(path)
        # print(open(path).read())
        # print(str(package_build))
        print(f'Checking whether {package_build} is released')
        if not get_release(package_build, use_token=True):
            print(f'{package_build} not released, building...')
            package_build.build_docker()
            package_build.copy_from_docker()
            print(f'Built {package_build} inside {package_build.build_directory()}')
            print('Releasing...')
            release_package(package_build)
        else:
            print(f'{package_build} already released, skipping...')
