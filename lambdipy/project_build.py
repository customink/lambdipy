import os
import shutil
import stat
import tarfile
import urllib
import sys


import docker
from requirementslib import Requirement


from .release import get_release


class NoReleaseCandidate(Exception):
    def __init__(self, requirement):
        super(NoReleaseCandidate, self).__init__()
        self.requirement = requirement

class NoReleaseAsset(Exception):
    def __init__(self, package_build):
        super(NoReleaseAsset, self).__init__()
        self.package_build = package_build

class ReleaseRequirementsMissmatched(Exception):
    def __init__(self, requirement, potential_candidates):
        super(ReleaseRequirementsMissmatched, self).__init__()
        self.requirement = requirement
        self.potential_candidates = potential_candidates


def get_requirements_from_pipenv():
    with os.popen("pipenv lock -r") as subprocess:
        return subprocess.read()


def _parse_requirement_line(line):
    if len(line) == 0:
        return None
    if line[:2] == '-i':
        return None

    return {
        "line": line,
        "requirement": Requirement.from_line(line)
    }


def parse_requirements(requirements_string):
    return list(filter(lambda x: x is not None, map(_parse_requirement_line, requirements_string.split('\n'))))


def resolve_requirements(requirements, package_builds):
    resolved_requirements = {}
    for requirement in requirements:
        name = requirement['requirement'].name
        if not name in package_builds:
            resolved_requirements[name] = None
        else:
            candidates = list(reversed(sorted(package_builds[name], key=lambda build: build.package_version)))
            predicate = lambda build: build.is_compatiple(requirement['requirement'], requirements)
            selected_candidate = next(filter(predicate, candidates), None)
            resolved_requirements[name] = selected_candidate
            if not selected_candidate:
                predicate = lambda build: build.version_matches(requirement['requirement'])
                potential_candidates = list(filter(predicate, candidates))
                if len(potential_candidates) > 0:
                    raise ReleaseRequirementsMissmatched(requirement['requirement'], potential_candidates)
                else:
                    raise NoReleaseCandidate(requirement['requirement'])

    for name, requirement in resolved_requirements.copy().items():
        if requirement is None:
            continue
        for pypi_dep_name, pypi_dep_specifier in requirement.pypi_dependencies():
            if not pypi_dep_name in resolved_requirements:
                candidates = list(reversed(sorted(package_builds[pypi_dep_name], key=lambda build: build.package_version)))
                requirement = _parse_requirement_line(''.join([pypi_dep_name, pypi_dep_specifier]))
                predicate = lambda build: build.is_compatiple(requirement['requirement'], requirements)
                selected_candidate = next(filter(predicate, candidates), None)
                if selected_candidate == None:
                    raise NoReleaseCandidate(requirement['requirement'])
                resolved_requirements[pypi_dep_name] = selected_candidate

    return resolved_requirements


def prepare_tarfile(url, download_filename, package_directory):
    urllib.request.urlretrieve(url, download_filename)
    tar = tarfile.open(download_filename, "r:gz")
    tar.extractall(package_directory)
    tar.close()

def download_and_prepare_asset(asset, package_release, package_build):
    url = asset.browser_download_url
    download_directory = os.environ['HOME'] + '/.lambdipy/packages/'
    os.makedirs(download_directory, exist_ok=True)
    print(f'Downloading {package_build.package_name} from GitHub release {package_release.tag_name}')
    download_filename = download_directory + os.path.basename(url)
    package_directory = download_directory + '/' + package_build.git_tag()
    prepare_tarfile(url, download_filename, package_directory)
    return download_directory + '/' + package_build.git_tag()


def build_and_prepare_package(package_build):
    print(f'Building {package_build.package_name} build version {package_build.git_tag()}')
    package_build.build_docker()
    package_build.copy_from_docker()
    return package_build.build_directory()


def find_package_in_cache(package_build):
    download_directory = os.environ['HOME'] + '/.lambdipy/packages/'
    package_directory = download_directory + '/' + package_build.git_tag()
    if os.path.isdir(package_directory):
        return package_directory


def prepare_resolved_requirements(resolved_requirements):
    package_paths = {}
    for package_name, package_build in resolved_requirements.items():
        if not package_build:
            continue
        cached_path = find_package_in_cache(package_build)
        if cached_path:
            package_paths[package_name] = cached_path
            print(f'Found {package_build.package_name} {package_build.git_tag()} in cache')
            continue

        use_token = os.environ.get('GITHUB_TOKEN') is not None
        package_release = get_release(package_build, use_token)
        if package_release:
            assets = package_release.get_assets()
            if assets.totalCount == 0:
                raise NoReleaseAsset(package_build)
            package_paths[package_name] = download_and_prepare_asset(assets[0], package_release, package_build)
        else:
            package_paths[package_name] = build_and_prepare_package(package_build)
    return package_paths


# https://stackoverflow.com/a/12514470/6871665
def _copytree(src, dest):
    os.makedirs(dest, exist_ok=True)
    if not os.path.isdir(src):
        shutil.copy2(src, dest)
    else:
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            if os.path.isdir(s):
                if not os.path.isdir(d):
                    shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)


def copy_prepared_releases_to_build_directory(package_paths, build_directory='./build'):
    shutil.rmtree(build_directory, ignore_errors=True)
    os.makedirs(build_directory, exist_ok=True)

    for _, directory in package_paths.items():
        for item in os.listdir(directory):
            _copytree(directory + '/' + item, build_directory + '/' + os.path.basename(item))


def _run_command_in_docker(command, build_directory):
    with open(build_directory + '/passwd', "w") as f:
        f.write(f'docker-build:x:{os.getuid()}:{os.getgid()}:docker-build,,,:/home:/bin/bash')

    # auth_sock = os.environ['SSH_AUTH_SOCK']
    # home = os.environ['HOME']
    # ssh_dir = f'{home}/.ssh'
    # volumes = {
    #     f'{os.path.abspath(build_directory)}/': {
    #         'bind': '/export/',
    #         'mode': 'rw'
    #     },
    #     f'{auth_sock}': {
    #         'bind': '/tmp/ssh_sock',
    #         'mode': 'ro'
    #     },
    #     f'{ssh_dir}': {
    #         'bind': '/home/.ssh',
    #         'mode': 'ro'
    #     },
    #     f'{os.path.abspath(build_directory)}/passwd': {
    #         'bind': '/etc/passwd',
    #         'mode': 'ro'
    #     }
    # }
    # environment = {
    #     'SSH_AUTH_SOCK': '/tmp/ssh_sock',
    #     'HOME': '/home'
    # }
    volumes = {
            f'{os.path.abspath(build_directory)}/': {
                'bind': '/tmp/export/',
                'mode': 'rw'
            }
    }
    environment = {
        'HOME': '/home'
    }

    environment_string = ' '.join([f'-e {key}={value}' for key, value in environment.items()])
    volumes_string = ' '.join([f'-v {key}:{value["bind"]}' for key, value in volumes.items()])
    user_string = f'--user {os.getuid()}:{os.getgid()}'

    if os.environ.get('PYTHON_VERSION', False):
        python_version = os.environ.get('PYTHON_VERSION')
    else:
        python_version = f'{sys.version_info.major}.{sys.version_info.minor}'

    docker_client = docker.from_env()
    docker_client.containers.run(
        f'lambci/lambda:build-python{python_version}',
        volumes=volumes,
        command=command,
        environment=environment,
        user=f'{os.getuid()}:{os.getgid()}'
    )
    # docker_command = f'docker run {environment_string} {volumes_string} {user_string} -it lambci/lambda:build-python3.6 {command}'
    # with os.popen(docker_command) as subprocess:
    #     print(subprocess.read())
    os.remove(build_directory + '/passwd')


def install_non_resolved_requirements(resolved_requirements, requirements, build_directory='./build'):
    packages_to_install = ''
    for requirement in requirements:
        if resolved_requirements[requirement['requirement'].name] is not None:
            continue
        requirement_line = requirement['line']
        packages_to_install += f' "{requirement_line}"'
    # GIT_SSH_COMMAND="/usr/bin/ssh -o StrictHostKeyChecking=no"
    install_command = f'pip install {packages_to_install} -t /tmp/export' if len(packages_to_install) > 0 else ''

    if len(packages_to_install) > 0:
        print(f'Installing remaining packages via pip:{packages_to_install}')

    with open(build_directory + '/build', "w") as f:
        f.writelines([
            '#!/bin/bash\n',
            'set -ex\n',
            install_command + '\n',
            'rm -rf /tmp/export/*.egg-info\n',
            'rm -rf /tmp/export/*.dist-info\n',
            'find /tmp/export/ -name __pycache__ | xargs rm -rf\n',
            'find /tmp/export/ -name tests | xargs rm -rf\n',
            'find /tmp/export/ -name "*.so" | xargs strip\n'
        ])
    st = os.stat(build_directory + '/build')
    os.chmod(build_directory + '/build', st.st_mode | stat.S_IEXEC)
    print(open(build_directory + '/build').read())

    _run_command_in_docker('/tmp/export/build', build_directory=build_directory)

    print('Finalizing the build')
    os.remove(build_directory + '/build')

def copy_include_paths(include_paths, build_directory='./build'):
    for path in include_paths:
        basename = os.path.basename(path)
        if len(basename) == 0:
            basename = path
        if os.path.isdir(path):
            shutil.copytree(path, build_directory + '/' + basename)
        else:
            shutil.copy2(path, build_directory + '/' + basename)
