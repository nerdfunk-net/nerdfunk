from pathlib import Path
import git
import os
import yaml
import logging
from yaml.loader import SafeLoader
from nerdfunk.utilities import misc


def get_file(config, properties):

    repo = properties.get('repo')
    filename = properties.get('filename')
    pull = properties.get('pull', False)

    if not repo or not filename:
        logging.error('repo and filename must be specified')
        return False

    # path to local directory of the repo
    git_path = misc.get_value_from_dict(config, ['git', repo, 'local_gitdir'])
    if git_path is None:
        logging.error(f'config error; local dir of {repo} does not exists')
        return False

    # the content may be in a subdir of the repo
    subdir = misc.get_value_from_dict(config, ['git', repo, 'local_content'])
    if subdir is None:
        subdir = "/"

    git_repo = git.Repo(git_path)
    if git_repo is None:
        logging.error(f'could not get repo {repo}')
        return False

    if git_repo is not None and pull:
        try:
            git_repo.remotes.origin.pull()
        except Exception as exc:
            logging.error("got exception %s" % exc)
            return False

    # check if path exists
    local_path = Path("%s/%s/%s" % (git_path, subdir, filename))
    if local_path.is_file():
        content = local_path.read_text()
    else:
        logging.error(f'file {local_path} does not exists')

    logging.debug(f'got content of file {local_path}')
    return content


def edit_file(config, *unnamed, **named):
    properties = dict(named)
    if unnamed:
        properties.update(unnamed[0])

    # init used variables
    content = {}
    name_of_repo = properties.get('repo')
    filename = properties.get('filename')
    if name_of_repo is None or filename is None:
        logging.error("config error; no repo or filename found")
        return False

    # path to local directory of the repo
    local_git_path = misc.get_value_from_dict(config, ['git', name_of_repo, 'local_gitdir'])

    # check if local path exists. If not raise an error
    if local_git_path is None:
        logging.error(f'config error; local dir of {name_of_repo} does not exists')
        return False

    # the content may be in a subdir of the repo
    subdir = misc.get_value_from_dict(config, ['git', name_of_repo, 'local_content'])
    if subdir is None:
        subdir = "/"

    if 'subdir' in properties:
        subdir += "/%s" % properties['subdir']

    # pull: True => do pull before writing context
    pull = properties.get('pull')

    logging.debug(f'git parameter: repo:{name_of_repo} local_git_path:{local_git_path} subdir:{subdir} pull:{pull}')

    # now try to get the GIT object
    repo = git.Repo(local_git_path)
    if repo is not None and pull:
        try:
            repo.remotes.origin.pull()
        except Exception as exc:
            return {'success': False,
                    'error': 'got exception %s' % exc}

    # we need the name of the current branch to push the update later
    current_branch = repo.active_branch.name

    content_filename = "%s/%s/%s" % (local_git_path, subdir, filename)
    # check if file exists
    if os.path.isfile(content_filename):
        comment = "updated %s in %s" % (filename, name_of_repo)
        logmessage = "%s updated in %s/%s" % (filename,
                                              current_branch,
                                              name_of_repo)
        # set id to 2 means updated in sot
        id = 2
        # check if the content of the two dicts must be merged
        if properties.get('action') == "merge":
            # merge file on disk and new config
            new_config = properties['content']
            with open(content_filename) as f:
                content = yaml.load(f, Loader=SafeLoader)
            content.update(new_config)
        else:
            # no merge; the config in properties is the one we use
            content = properties['content']
    else:
        # it is a new file, set id to 0
        id = 0
        comment = "%s in %s/%s added to sot" % (filename, current_branch, name_of_repo)
        logmessage = "%s in %s/%s added to sot" % (filename, current_branch, name_of_repo)
        content = properties['content']

    # write content to to disk
    with open(content_filename, "w") as filehandler:
        filehandler.write(content)
        filehandler.close()

    # add file to git
    # even the file exists before writing the new config to the local
    # file leads to the situation that the file must be added to our repo
    repo.index.add(content_filename)

    # commit changes
    repo.index.commit(comment)
    # try:
    #     repo.remotes.origin.push(refspec=current_branch)
    # except Exception as exc:
    #     return {'success': False,
    #             'error': 'got exception %s' % exc}

    logging.debug(logmessage)
    return True