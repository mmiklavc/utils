#!/usr/bin/python

from optparse import OptionParser
from requests.auth import HTTPBasicAuth
import datetime
import os
import os.path
import zlib
import getpass
import requests
import json
import sys

class UserPrompt(object):
    
    def __init__(self, prompt):
        self.prompt = prompt

    def get_hidden(self):
        return getpass.getpass(self.prompt)

class FileWriter(object):

    def write(self, path, content):
        print "Writing config to " + path
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        with open(path, 'w') as outfile:
            outfile.write(content)
        print "Done writing " + path

class InfoGatherer(object):

    def __init__(self, name, host_info):
        self.name = name
        self.host_info = host_info

    def get_info_type(self):
        return self.name

class AmbariInfo(InfoGatherer):

    def __init__(self, host_info, cluster_name):
        super(AmbariInfo, self).__init__('Ambari', host_info)
        self.cluster_name = cluster_name
        self.ambari_config_url = 'http://{0}/api/v1/clusters/{1}/configurations/service_config_versions'.format(host_info, cluster_name)
        self.params_payload = { 'is_current' : 'true' }

    def get_host(self):
        return self.host_info

    def collect(self, out_dir):
        print "Ambari request URL: " + self.ambari_config_url
        ambari_user = UserPrompt('Ambari username: ').get_hidden()
        ambari_pass = UserPrompt('Ambari password: ').get_hidden()
        self.get_cluster_config(out_dir, ambari_user, ambari_pass)

    def get_cluster_config(self, out_dir, ambari_user, ambari_pass):
        # set encoding to 'identity' to keep Ambari from passing back gzipped content for large requests
        headers = {
                    'X-Requested-By' : 'ambari',
                    'Authorization' : 'Basic',
                    'Accept-Encoding': 'identity'
                  }
        # Retrieving Ambari config detail
        response = requests.get(self.ambari_config_url, headers=headers, params=self.params_payload, stream=True, auth=HTTPBasicAuth(ambari_user, ambari_pass))
        if response.status_code == 200:
            file_name = 'ambari-cluster-config.json'
            full_out_path = os.path.join(out_dir, self.name.lower(), file_name)
            FileWriter().write(full_out_path, response.text)
        else:
            print "Request failed with status code: " + str(response.status_code)

class StormInfo(InfoGatherer):

    def __init__(self, host_info):
        super(StormInfo, self).__init__('Storm', host_info)
        self.storm_url = 'http://{0}/api/v1/topology/summary'

    def get_host(self):
        return self.host_info

    def collect(self):
        pass

class KafkaInfo(InfoGatherer):

    def __init__(self, host_info):
        super(KafkaInfo, self).__init__('Kafka', host_info)

    def get_host(self):
        return self.host_info

    def collect(self):
        pass

class ZookeeperInfo(InfoGatherer):

    def __init__(self, host_info):
        super(ZookeeperInfo, self).__init__('Zookeeper', host_info)

    def get_host(self):
        return self.host_info

    def collect(self):
        pass

class MetronInfo(InfoGatherer):

    def __init__(self, host_info):
        super(MetronInfo, self).__init__('Metron', host_info)

    def get_host(self):
        return self.host_info

    def collect(self):
        pass

class HdpInfo(InfoGatherer):

    def __init__(self, host_info):
        super(HdpInfo, self).__init__('HDP', host_info)

    def get_host(self):
        return self.host_info

    def collect(self):
        pass

class ClusterInfo:

    def __init__(self):
        pass

    def main(self):
        (options, args) = self.get_cli_args()
        self.collect_data(options.out_dir,
                          options.ambari_host,
                          options.cluster_name,
                          options.storm_host,
                          options.broker_list,
                          options.zookeeper_quorum,
                          options.metron_home,
                          options.hdp_home)

    def get_cli_args(self):
        parser = OptionParser()
        parser.add_option("-a", "--ambari-host", 
                          action="store",
                          type="string",
                          dest="ambari_host",
                          help="Connect to Ambari via the supplied host:port",
                          default="node1:8080",
                          metavar="HOST:PORT")
        parser.add_option("-c", "--cluster-name", 
                          action="store",
                          type="string",
                          dest="cluster_name",
                          help="Name of cluster in Ambari to retrieve info for",
                          default="metron_cluster",
                          metavar="NAME")
        parser.add_option("-o", "--out-dir", 
                          action="store",
                          type="string",
                          dest="out_dir",
                          help="Write debugging data to specified root directory",
                          default=".",
                          metavar="DIRECTORY")
        parser.add_option("-s", "--storm-host", 
                          action="store",
                          type="string",
                          dest="storm_host",
                          help="Connect to Storm via the supplied host:port",
                          default="node1:8744",
                          metavar="HOST:PORT")
        parser.add_option("-b", "--broker_list", 
                          action="store",
                          type="string",
                          dest="broker_list",
                          help="Connect to Kafka via the supplied comma-delimited host:port list",
                          default="node1:6667",
                          metavar="HOST1:PORT,HOST2:PORT")
        parser.add_option("-z", "--zookeeper_quorum", 
                          action="store",
                          type="string",
                          dest="zookeeper_quorum",
                          help="Connect to Zookeeper via the supplied comma-delimited host:port quorum list",
                          default="node1:2181",
                          metavar="HOST1:PORT,HOST2:PORT")
        parser.add_option("-m", "--metron_home", 
                          action="store",
                          type="string",
                          dest="metron_home",
                          help="Metron home directory",
                          default="/usr/metron/0.4.3",
                          metavar="DIRECTORY")
        parser.add_option("-p", "--hdp_home", 
                          action="store",
                          type="string",
                          dest="hdp_home",
                          help="HDP home directory",
                          default="/usr/hdp/current",
                          metavar="DIRECTORY")

        return parser.parse_args()
    
    def collect_data(self, 
                     out_dir_base,
                     ambari_host,
                     cluster_name,
                     storm_host,
                     broker_list,
                     zookeeper_quorum,
                     metron_home,
                     hdp_home):
        out_dir = os.path.join(out_dir_base, 'metron-debug-' + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
        info_getters = [
                AmbariInfo(ambari_host, cluster_name),
                StormInfo(storm_host),
                KafkaInfo(broker_list),
                ZookeeperInfo(zookeeper_quorum),
                MetronInfo(metron_home),
                HdpInfo(hdp_home)
        ]
        #for getter in info_getters:
        #    getter.collect()
        info_getters[0].collect(out_dir)

if __name__ == "__main__":
    ClusterInfo().main()

