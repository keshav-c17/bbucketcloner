import argparse
import os
import shutil
import sys
from typing import Union, List, Optional

import git
import requests


def add_credentials(url: str, user: str, password: str) -> Union[str, None]:
    """Adding username and password to the URL.
    URL may contain the username in the form of http(s)://user@example.com
    or just the url http(s)://example.com and will return
    https://user:password@example.com

    Args:
        url (str): source url
        user (str): username
        password (str): password

    Returns:
        str: url with credentials, None if invalid url
    """
    if '@' in url:
        repo = url.split('@')[1]
    elif '//' in url:
        repo = url.split('//')[1]
    else:
        print(f'Invalid URL: {url}')
        return None
    url = 'https://' + user + ':' + password + '@' + repo
    return url


def _clone_bitbucket_workspace(user: str, password: str, workspace: str, skip_existing: bool = True, project: Optional[str] = None) -> None:
    """Cloning all repositories

    Args:
        user (str): username
        password (str): password
    """

    url = f'https://api.bitbucket.org/2.0/repositories/{workspace}?pagelen=10'
    if project:
        url = url + f"&q=project.key%3D%22{project}%22"

    while (resp := requests.get(url, auth=(user, password))).status_code == 200:
        jresp = resp.json()

        for repo in jresp['values']:
            if repo['scm'] == 'git':

                # Checking if there is a https clone link
                repo_url = None
                for clone in repo['links']['clone']:
                    if clone['name'] == 'https':
                        repo_url = clone['href']
                        break

                if repo_url is None:
                    print(f'Skipping {repo["name"]} because there is no https clone link.')
                    continue

                print(f'Cloning {repo["name"]} from {repo_url} into {workspace}.')
                if os.path.exists(f'{workspace}/{repo["name"]}'):
                    if skip_existing:
                        print(f'Skipping {workspace}/{repo["name"]} because it already exists.')
                        continue
                    else:
                        print(f'Deleting {workspace}/{repo["name"]} because it already exists.')
                        shutil.rmtree(f'{workspace}/{repo["name"]}')
                repo_url = add_credentials(repo_url, user, password)
                git.Repo.clone_from(repo_url, f'{workspace}/{repo["name"]}')

            else:
                print(f'Skipping {repo["name"]} because it is not a git but a {repo["scm"]} repository.')

        if 'next' not in resp.json():
            break
        url = resp.json()['next']
    else:
        print(f'The url {url} returned status code {resp.status_code}.')


def clone_bitbucket(user: str, password: str, workspaces: Union[str, None], skip_existing: bool = True, project: Optional[str] = None) -> None:
    """Cloning all repositories

    Args:
        user (str): username
        password (str): password
        workspaces (str | None): workspace name
        skip_existing (bool): skip existing repositories
    """
    if workspaces is None:
        workspaces = [w['slug'] for w in list_bitbucket_workspaces(user, password)]
    else:
        workspaces = workspaces.split(',')

    for workspace in workspaces:
        if not os.path.exists(workspace):
            os.mkdir(workspace)
        _clone_bitbucket_workspace(user, password, workspace, skip_existing, project)


def list_bitbucket_workspaces(user: str, password: str) -> list:
    """List all workspaces

    Args:
        user (str): username
        password (str): password

    Returns:
        list: List of workspaces (dict with name, slug, and url as entries)
    """
    url = "https://api.bitbucket.org/2.0/workspaces"

    workspaces = []

    while (resp := requests.get(url, auth=(user, password))).status_code == 200:
        jresp = resp.json()

        for workspace in jresp['values']:
            w = {
                'name': workspace['name'],
                'slug': workspace['slug'],
                'url': workspace['links']['html']['href']
            }
            workspaces.append(w)

        if 'next' not in resp.json():
            break
        url = resp.json()['next']

    else:
        print(f'The url {url} returned status code {resp.status_code}.')

    return workspaces


def list_bitbucket_projects(user: str, password: str, workspace_slug: str):
    """List all projects

    Args:
        user (str): username
        password (str): password
        workspace_slug (str): workspace slug
    Returns:
        list: List of project names in a workspace
    """
    url = f"https://api.bitbucket.org/2.0/workspaces/{workspace_slug}/projects"

    projects = []

    resp = requests.get(url, auth=(user, password))

    if resp.status_code == 200:
        json_resp = resp.json()
        for project in json_resp['values']:
            projects.append(project['name'])

    return projects


def clone_projects(user: str, password: str):
    root_path = input("Enter path where projects will be cloned: ").strip()
    workspace_name = input("Enter target bitbucket workspace keyword: ").strip()
    if workspace_name != "":
        chars_to_replace = [" ", "-", "/", "\\"]
        replaced_char = "_"
        if os.path.exists(root_path):
            workspaces = list_bitbucket_workspaces(user, password)
            target_hit = []
            for w in workspaces:
                w_slug = w['slug']
                total_projects = 0
                total_repos_in_w = 0
                if workspace_name in w_slug:
                    target_hit.append(True)
                    print(f'\nWorkspace found: {w["name"]} ({w_slug}) - {w["url"]}')
                    w_folder_name = ''.join([replaced_char if char in chars_to_replace else char for char in w_slug]).lower()
                    projects_api_url = f"https://api.bitbucket.org/2.0/workspaces/{w_slug}/projects"
                    resp = requests.get(projects_api_url, auth=(user, password))
                    if resp.status_code == 200:
                        projects = resp.json()['values']
                        for project in projects:
                            total_projects += 1
                            total_repos_in_proj = 0
                            project_name = project['name']
                            print(f"Project Name: {project_name}")
                            project_folder_name = ''.join([replaced_char if char in chars_to_replace else char for char in project_name]).lower()
                            repositories_api_url = project['links']['repositories']['href']
                            get_repos_resp = requests.get(repositories_api_url, auth=(user, password))
                            if get_repos_resp.status_code == 200:
                                repositories = get_repos_resp.json()['values']
                                for repo in repositories:
                                    total_repos_in_proj += 1
                                    repo_name = repo['name']
                                    if repo['scm'] == 'git':
    
                                        # Checking if there is a https clone link
                                        repo_url = None
                                        for clone in repo['links']['clone']:
                                            if clone['name'] == 'https':
                                                repo_url = clone['href']
                                                break
    
                                        if repo_url is None:
                                            print(f'Skipping {repo["name"]} because there is no https clone link.')
                                            continue
    
                                        project_path = os.path.join(root_path, w_folder_name, project_folder_name)
                                        repo_path = os.path.join(project_path, repo_name.lower())
                                        if not os.path.exists(repo_path):
                                            repo_url = add_credentials(repo_url, user, password)
                                            print(f'  |__Cloning {repo["name"]} to {repo_path}..')
                                            git.Repo.clone_from(repo_url, repo_path)
                                        else:
                                            print(f'  |__Skipping {repo["name"]} because it already exists.')
                                            continue
                                    else:
                                        print(f'Skipping {repo["name"]} because it is not a git but a {repo["scm"]} repository.')
                                print(f"Total number of repos in this project: {total_repos_in_proj}")
                                total_repos_in_w += total_repos_in_proj
                        print(f"Total Projects: {total_projects}, Total Repos in this workspace: {total_repos_in_w}")
                else:
                    target_hit.append(False)
            if not any(target_hit):
                print(target_hit)
                print("Entered keyword did not match with any bitbucket workspace..")
        else:
            print("Invalid path, aborting..")
    else:
        print("Invalid keyword entered, aborting..")


def main(args: List[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', help='Username', required=True)
    parser.add_argument('-p', '--password', help='App password', required=True)
    parser.add_argument('-w', '--workspace', help='Workspace name(s), separated by comma')
    parser.add_argument('-s', '--skip-existing', help='Skip existing repositories', action='store_true')
    parser.add_argument('--project', help='Limit the clone to a specifc bitbucket project')
    parser.add_argument('command', help='Command', choices=['clone', 'workspace', 'list_projects', 'clone_projects'])

    namespace = parser.parse_args(args)

    if namespace.command == 'clone':
        clone_bitbucket(namespace.user, namespace.password, namespace.workspace, namespace.skip_existing, namespace.project)

    elif namespace.command == 'workspace':
        workspaces = list_bitbucket_workspaces(namespace.user, namespace.password)
        for w in workspaces:
            print(f'{w["name"]} ({w["slug"]}) - {w["url"]}')
    elif namespace.command == 'list_projects':
        workspaces = list_bitbucket_workspaces(namespace.user, namespace.password)
        for w in workspaces:
            slug = w['slug']
            print(f'\n{w["name"]} ({w["slug"]}) - {w["url"]}')
            print(list_bitbucket_projects(namespace.user, namespace.password, slug))
    elif namespace.command == 'clone_projects':
        clone_projects(namespace.user, namespace.password)


def entry_point():
    main(sys.argv[1:])


if __name__ == '__main__':
    entry_point()
