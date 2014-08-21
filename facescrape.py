# Copyright 2014 Sam Fishman
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Facescrape is a tool for scraping the Harvard College Facebook.

Usage:
>>> fs = FaceScraper(my_huid, my_pw)
>>> data = fs.scrape_students({'house': 'Kirkland House'})
>>> fs.export_csv('/path/to/export.csv')
"""

import csv
import re
import requests

LOGIN_URL = "https://www.pin1.harvard.edu/cas/login?service=https%3A%2F%2Fwww.pin1.harvard.edu%2Fpin%2Fauthenticate%3F__authen_application%3DFAS_CS_FACEBOOK%26original_request%3D%2Fsearchform"
INDEX_URL = "http://facebook.college.harvard.edu//search"
INDIVIDUAL_URL = "http://facebook.college.harvard.edu//individual?id=%s"

class FaceScraper(object):
    def __init__(self, huid, pw):
        self.username = str(huid)
        self.pw = str(pw)

    def login(self):
        self.jar = {}
        login_page = requests.get(LOGIN_URL)
        lt = re.findall(r'<input type="hidden" name="lt" value="([\w\-]+)',
                login_page.text)[0]
        ex = re.findall(r'<input type="hidden" name="execution" value="(\w+)',
                login_page.text)[0]
        self.jar.update(login_page.cookies)
        last = requests.post(LOGIN_URL, data={
                'compositeAuthenticationSourceType': 'PIN',
                'username': self.username,
                'password': self.pw,
                '_eventId_submit': 'Login',
                'lt': lt,
                'execution': ex,
                'casPageDisplayType': 'DEFAULT',
                'nonMobileOptionOnMobile': ''},
            allow_redirects=False, cookies=self.jar)
        while last.status_code == 302:
            self.jar.update(last.cookies)
            last = requests.get(last.headers['location'], cookies=self.jar,
                    allow_redirects=False)
        try:
            del self.jar['CASTGC']
        except KeyError:
            raise Exception('Login Failed!')

    def scrape_students(self, filters=None):
        self.login()
        payload = {'name_last': '', 'name_first': '', 'house': '',
                'assigned_house': '', 'year': '', 'concentration': '',
                'num': '9999', 'Search': 'Search', 'view': 'photo'}
        if filters:
            payload.update(filters)
        index = requests.get(INDEX_URL, params=payload, cookies=self.jar,
                            allow_redirects=False)
        ids = re.findall(
                r'<div class="photo">\n<a href="individual\?id=([a-f0-9]+)',
                index.text)
        ans = map(self.get_student, ids)
        self.last_read = ans
        return ans
        
    def get_student(self, sid):
        r = requests.get(INDIVIDUAL_URL % sid, cookies=self.jar)
        body = r.text.replace('<br>', '')
        data = {}

        for key in ('Name', 'House', 'Year', 'Concentration', 'Assigned House',
                    'Dorm Address', 'Mail Address'):
            match = re.search(
                    r'<span class="field">%s:</span><span class="value">'
                    r'([\w\-\', ]+)<' % key, body)
            if match:
                data[key.lower()] = match.group(1)
            else:
                data[key.lower()] = None

        for key, pat in [('email', r'mailto:([\w\-\.]+@college\.harvard\.edu)'),
                ('photo', r'<img alt="Image" width="250" src="([\w/\-\.]+)"')]:
            match = re.search(pat, body)
            if match:
                data[key] = match.group(1)
            else:
                data[key] = None

        data['photo'] = 'http://facebook.college.harvard.edu/%s' % data['photo']

        return data

    def export_csv(self, path, columns=None):
        if columns == None:
            columns = ('Name', 'House', 'Year', 'Concentration',
                       'Assigned House', 'Dorm Address', 'Mail Address',
                       'Email', 'Photo')
        with open(path, 'w') as f:
            exporter = csv.writer(f)
            exporter.writerow(columns)
            rows = map(lambda p: [p[c.lower()] if c.lower() in p else ''
                                  for c in columns],
                       self.last_read)
            exporter.writerows(rows)

