#!/usr/bin/python

import requests
import json
import sys

host = 'http://node1:8744'
if len(sys.argv) > 1:
    host = sys.argv[1]

url = '{0}/api/v1/topology/summary'.format(host)

response = requests.get(url)

for feature, value in response.json().iteritems():
    if feature == 'topologies':
        for topology in value:
            for k, v in topology.iteritems():
                if k == 'id':
                    print v

