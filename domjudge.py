#!/usr/bin/env python
"""Downloads student answers from DOMJudge

Requires:
    a username and password for the judge
    an internet connection to actually download the bibliography    
    
How to run:
    1. get a virtual environment installed: python3 -m venv domjudge
    2. activate it: source domjudge/bin/activate
    3. install dependencies: pip install -r requirements.txt
       
"""

import requests
from bs4 import BeautifulSoup
import os
import argparse
import json

def download_submissions(url, verify_ssl, username, password, contest_id, problem_ids):

    valid_ids = set(problem_ids)

    # login
    s = requests.Session()
    soup = BeautifulSoup(s.get(f'{url}/login', verify=verify_ssl).text, 'html.parser')
    csrf_token = soup.find('input', {'name': '_csrf_token'})['value']
    print(f"Logging in - csrf token is {csrf_token}...")
    r = s.post(url+'/login', data={'_username': username, '_password': password, '_csrf_token': csrf_token})
    if r.status_code != 200 or r.url != f'{url}/jury':
        print(f"  ... failed to login. Status code is {r.status_code}, landed at {r.url}")
        return False
    else:
        print(f"  ... logged in successfully. Now attempting to download submissions for {problem_ids}")

    # get list of submissions
    sub_url = f'{url}/api/v4/submissions'
    print(f"  ... getting list of submissions from {sub_url}")
    r = s.get(sub_url)
    if r.status_code != 200:
        print(f"  ... failed to get list of submissions. Status code is {r.status_code}, text follows\n{r.text}")
        return False
    data = r.json()
    print(f"  ... got {len(data)} submissions, filtering for those in {valid_ids}")
    submissions_by_problem = {}
    for sub in data:
        problem_id = sub['problem_id']
        if problem_id in valid_ids: 
            if problem_id not in submissions_by_problem:
                submissions_by_problem[problem_id] = []
            submissions_by_problem[problem_id].append(sub)
    
    for problem_id in problem_ids:
        problem_id = f"{problem_id}"
        print(f"  ... found {len(submissions_by_problem[problem_id])} for problem {problem_id}")
        if not os.path.isdir(problem_id):
            os.mkdir(problem_id)

        for sub in submissions_by_problem[problem_id]:
            submission_id = sub['id']
            team = sub['team_id']
            # 2025-02-18T16:36:10.674+01:00 -> 2025-02-18_16-36
            date = sub['time'][:16].replace('T', '_').replace(':', '-')
            print(f"  ... downloading submission {submission_id} ({sub})")
            r = s.get(f'{url}/jury/submissions/{submission_id}')
            soup = BeautifulSoup(r.text, 'html.parser')
            verdict = soup.css.select_one('div.mb-2>div>span.sol').string
            print(f"  ... verdict: {verdict}")
            
            # download submission ids
            dirname = f'{problem_id}/{team}/{submission_id}_{date}_{team}_{verdict}'
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            r = s.get(f'{url}/jury/submissions/{submission_id}/source')
            fideo = BeautifulSoup(r.text, 'html.parser')
            sources = fideo.find_all('a', {'class': 'nav-link', 'role': 'tab'})

            # download files themselves
            file_index = 0
            for current_file in sources:
                filename = f'{dirname}/{current_file.string}'
                if (os.path.isfile(filename)):
                    continue
                filename_url = f'{url}/jury/submissions/{submission_id}/source?fetch={file_index}' 
                print(f'GET {filename_url} -> {filename}', end='')
                try:
                    # see https://stackoverflow.com/a/16696317/15472
                    with s.get(filename_url, stream=True) as req:
                        req.raw.decode_content = True # fix gzip encoding
                        req.raise_for_status()
                        with open(filename, 'wb') as f:
                            for chunk in req.iter_content(chunk_size=8192): 
                                f.write(chunk)
                except Exception as e:
                    print(f'\nFailed! {e}')
                print()
                file_index += 1

if __name__ == '__main__':      
    parser = argparse.ArgumentParser(description=\
        "Download submissions for a set of problems from a given domjudge server.")
    parser.add_argument("--url", 
            help="The URL to the domjudge server", default="https://ed.fdi.ucm.es/domjudge")
    parser.add_argument("--verify_ssl",
            help="Whether to verify the SSL certificate", default=True)
    parser.add_argument("--credentials",
            help="A JSON file with username & password for a judge on that server", default="credentials.json")
    parser.add_argument("--contest",
            help="The name of the contest in which the problem can be found", default="5")
    parser.add_argument("--problems",
            help="Comma-separated problem IDs to download", nargs="+", default=None)
    args=parser.parse_args()

    if (args.problems is None):
        print("No problems specified. Use --problems to specify the problems to download.")
        exit(1)
    
    with open(args.credentials) as f:
        credentials = json.load(f)
    if download_submissions(args.url, args.verify_ssl, 
                         credentials['username'], credentials['password'],
                         args.contest, 
                         args.problems):
        exit(0)
    else:
        exit(1)
