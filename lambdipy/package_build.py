from collections import defaultdict
import glob
import io
import json
import os
import re
import shutil
import tarfile


import docker
from packaging.specifiers import SpecifierSet


def build_package_build_dict(paths):
    package_builds = map(lambda x: PackageBuild(x), paths)

    package_builds_dict = defaultdict(list)
    for build in package_builds:
        package_builds_dict[build.package_name] += [build]
    return package_builds_dict


class PackageBuild:
    def __init__(self, build_info_path):
        self.package_name, self.package_version, config_name = build_info_path.split('/')[-3:]
        with open(build_info_path) as f:
            self.build_info = json.load(f)
        config_version_search = re.search('build\.(.+)\.json', config_name)
        self.config_version = config_version_search.group(1) if config_version_search else None
        self.build_version = self.build_info['build-version']
        self.docker_client = docker.from_env()

    def yum_dependencies(self):
        return self.build_info['dependencies'].get('yum', [])

    def pypi_dependencies(self):
        return self.build_info['dependencies'].get('pypi', [])

    def command_dependencies(self):
        return self.build_info['dependencies'].get('commands', None)

    def python_setup(self):
        return self.build_info['dependencies'].get('setup_python', None)

    def libs_to_copy(self):
        return self.build_info.get('libs', [])

    def _dockerfile(self):
        yum_dependencies_string = ' '.join(self.yum_dependencies())
        pypi_dependencies_string = ' '.join(map(lambda x: f'"{x[0]}{x[1]}"', self.pypi_dependencies()))

        dockerfile_string = f'FROM {self.build_container_image()}\n'

        if self.python_setup() is not None:
            workdir = self.python_setup().get('workdir', '/root')
            yum_dependencies_string += f' python3 python3-devel which git tar gcc make zlib-devel bzip2-devel readline-devel openssl-devel libffi-devel'
            dockerfile_string += f'WORKDIR {workdir}\n'

        dockerfile_string += 'RUN set -x && yum update -y\n'
        if len(self.yum_dependencies()) > 0:
            dockerfile_string += f'RUN set -x && yum -y install {yum_dependencies_string}\n'
        if self.command_dependencies() is not None:
            for command in self.command_dependencies():
                dockerfile_string += f'RUN set -x && {command}\n'
        if self.python_setup() is not None:
            pipenv_version = self.python_setup().get('pipenv', '2018.11.26')
            python_version = self.python_setup().get('python', '3.6')
            home = self.python_setup().get('home', '/root')
            dockerfile_string += f'RUN set -x && pip3 install "pipenv=={pipenv_version}"\n'
            dockerfile_string += f'RUN set -x && git clone https://github.com/pyenv/pyenv.git ~/.pyenv\n'
            dockerfile_string += f'ENV PYENV_ROOT="{home}/.pyenv"\n'
            dockerfile_string += 'ENV PATH="$PYENV_ROOT/bin:$PATH"\n'
            dockerfile_string += 'RUN set -x && eval "$(pyenv init -)"\n'
            dockerfile_string += f'RUN set -x && pyenv install {python_version}\n'
            dockerfile_string += 'RUN set -x && touch Pipfile\n'
            dockerfile_string += f'RUN set -x && pipenv --python {python_version}\n'
        if len(self.pypi_dependencies()) > 0:
            dockerfile_string += f'RUN set -x && pipenv run pip install {pypi_dependencies_string}\n'

        dockerfile_string += f'RUN set -x && pipenv run pip install {self._no_binary_flag()} {self.package_name}=={self.package_version} -t prebuilt\n'

        if self.build_info.get('exclude-subpackages', False):
            dockerfile_string += '\n'.join(list(map(lambda x: f'RUN set -x && rm -rf prebuilt/{x}*', self.build_info.get('exclude-subpackages'))))
        return dockerfile_string

    def build_container_image(self):
        return self.build_info.get('docker', {}).get('image', 'lambci/lambda:build-python3.6')

    def _no_binary_flag(self):
        allow_binaries = self.build_info.get('allow-binaries', False)
        return '' if allow_binaries else f'--no-binary {self.package_name}'

    def docker_tag(self):
        tag = f'lambdipy/{self.package_name}:{self.package_version}-{self.build_version}'
        if self.config_version:
            tag += f'-{self.config_version}'
        return tag

    def git_tag(self):
        tag = f'{self.package_name}-{self.package_version}'
        if self.config_version:
            tag += f'-{self.config_version}'
        tag += f'-{self.build_version}'
        return tag

    def build_docker(self, verbose=False):
        if verbose:
            print()
            print(self._dockerfile())

        dockerfile = io.BytesIO(bytes(self._dockerfile(), encoding='utf-8'))

        cli = docker.APIClient()
        build_runtime = cli.build(fileobj=dockerfile, tag=self.docker_tag(), pull=True, rm=True)
        print(f'Building docker image {self.docker_tag()}')
        line_buffer = ''
        for line in (line for chunk in build_runtime for line in chunk.decode('utf-8').split('\n') if len(line) > 0):
            if verbose:
                line_buffer += line
                try:
                    decoded_line = json.loads(line_buffer)
                    line_buffer = ''
                except json.decoder.JSONDecodeError:
                    continue
                if 'stream' not in decoded_line:
                    continue
                print(decoded_line['stream'], end='')
            else:
                print('.', end='')
        print()

    def build_directory(self):
        home = os.environ['HOME']
        directory = f'{home}/.lambdipy/build/{self.package_name}/{self.package_version}'
        if self.config_version:
            directory += f'/{self.config_version}'
        return directory

    def _docker_volumes(self):
        return {
            f'{self.build_directory()}/': {
                'bind': '/tmp/export/',
                'mode': 'rw'
            }
        }

    def _run_command_in_docker(self, command):
        self.docker_client.containers.run(
            self.docker_tag(),
            volumes=self._docker_volumes(),
            command=command,
            user=f'{os.getuid()}:{os.getgid()}'
        )

    def copy_from_docker(self):
        shutil.rmtree(self.build_directory(), ignore_errors=True)
        os.makedirs(self.build_directory(), exist_ok=True)

        self._run_command_in_docker('bash -c "cp -r prebuilt/* /tmp/export/"')
        if len(self.libs_to_copy()) > 0:
            os.mkdir(f'{self.build_directory()}/lib')
            self._run_command_in_docker(f'bash -c "cp ' + ' '.join(self.libs_to_copy()) + ' /tmp/export/lib"')

    def create_compressed_tarball(self):
        home = os.environ['HOME']
        tarball_path = f'{home}/.lambdipy/build/{self.git_tag()}.tar.gz'
        with tarfile.open(tarball_path, "w:gz") as tar:
            for path in glob.glob(f'{self.build_directory()}/*'):
                tar.add(path, arcname=os.path.basename(path))

        return tarball_path

    def _check_requirements_dependency_match(self, dependency_name, dependency_specifiers, requirements):
        matching_requirement = next(filter(lambda x: x['requirement'].name == dependency_name, requirements), None)
        if not matching_requirement:
            return True
        matching_requirement_version = matching_requirement['requirement'].req.version.replace('=', '')
        return SpecifierSet(dependency_specifiers).contains(matching_requirement_version)

    def version_matches(self, requirement):
        specifier_set = SpecifierSet(requirement.specifiers)
        return specifier_set.contains(self.package_version)

    def is_compatiple(self, requirement, requirements):
        version_match = self.version_matches(requirement)
        if len(self.pypi_dependencies()) > 0:
            for dependency_name, dependency_specifiers in self.pypi_dependencies():
                version_match = version_match and self._check_requirements_dependency_match(dependency_name, dependency_specifiers, requirements)
        return version_match

    def __str__(self):
        return f'{self.package_name} {self.package_version} {self.config_version}'
