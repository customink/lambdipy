import os


from github import Github, InputGitAuthor
from github.GithubException import UnknownObjectException
from github.GitRelease import GitRelease


OWNER = os.environ.get('GIT_OWNER', 'customink')
REPO = os.environ.get('GIT_REPO', 'lambdipy')

RELEASE_AUTHOR = os.environ.get('GIT_AUTHOR', 'adikus')
RELEASE_AUTHOR_EMAIL = os.environ.get('GIT_AUTHOR_EMAIL', 'andrej.hoos@gmail.com')


def _get_release_by_tag(tag, use_token):
    if use_token:
        token = os.environ.get('GITHUB_TOKEN', False) or open('.token').readline().replace('\n', '')
        g = Github(token)
    else:
        g = Github()
    repo = g.get_user(OWNER).get_repo(REPO)
    headers, data = repo._requester.requestJsonAndCheck(
        "GET",
        repo.url + f'/releases/tags/{tag}'
    )
    return GitRelease(repo._requester, headers, data, completed=True)


def get_release(build, use_token=False):
    try:
        return _get_release_by_tag(build.git_tag(), use_token=use_token)
    except UnknownObjectException:
        return False


def release(build):
    token = os.environ.get('GITHUB_TOKEN', False) or open('.token').readline().replace('\n', '')
    g = Github(token)
    repo = g.get_user(OWNER).get_repo(REPO)
    author = InputGitAuthor(RELEASE_AUTHOR, RELEASE_AUTHOR_EMAIL)
    commit = repo.get_branch('master').commit.sha
    message = 'Automatic release containing a package built for AWS Lambda environment'

    release = repo.create_git_tag_and_release(
        tag=build.git_tag(),
        tag_message=message,
        release_name=f'Prebuilt package of {build.package_name} {build.package_version}',
        release_message=message,
        object=commit,
        type='commit',
        tagger=author
    )
    release_path = build.create_compressed_tarball()
    release.upload_asset(release_path, release_path.split('/')[-1], 'application/gzip')
