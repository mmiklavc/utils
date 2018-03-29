#!/usr/bin/python

from optparse import OptionParser
from requests.auth import HTTPBasicAuth
from contextlib import closing
import datetime
import os
import os.path
import zlib
import getpass
import requests
import json
import subprocess
import sys
import tarfile

INDENT_SIZE = 2

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
        print "...done"

class ShellHandler(object):

    def __init__(self):
        pass

    # returns full stdout of process call
    def call(self, command):
        try:
            return subprocess.call(command)
        except OSError as e:
            print >> sys.stderr, "Execution failed:", e
    
    # partly hijacked from Python 2.7+ check_output for use in 2.6
    def ret_output(self, cmd):
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            raise subprocess.CalledProcessError(retcode, cmd, output=output)
        return output

class InfoGatherer(object):

    def __init__(self, name):
        self.name = name

class AmbariInfo(InfoGatherer):

    def __init__(self, host_info, cluster_name):
        super(AmbariInfo, self).__init__('Ambari')
        self.cluster_name = cluster_name
        self.ambari_config_url = 'http://{0}/api/v1/clusters/{1}/configurations/service_config_versions'.format(host_info, cluster_name)
        self.params_payload = { 'is_current' : 'true' }

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
        super(StormInfo, self).__init__('Storm')
        url_base = 'http://{0}/api/v1'.format(host_info)
        self.url_cluster_summary = url_base + '/cluster/summary'
        self.url_cluster_configuration = url_base + '/cluster/configuration'
        self.url_topology_summary = url_base + '/topology/summary'
        self.url_topology_stats_summary = url_base + '/topology/{0}?sys=1'

    def collect(self, out_dir):
        self.get_cluster_summary(out_dir)
        self.get_cluster_configuration(out_dir)
        self.get_topology_summary(out_dir)
        self.get_topology_stats_summary(out_dir)

    def get_cluster_summary(self, out_dir):
        response = requests.get(self.url_cluster_summary)
        if response.status_code == 200:
            file_name = 'cluster-summary.json'
            full_out_path = os.path.join(out_dir, self.name.lower(), file_name)
            FileWriter().write(full_out_path, json.dumps(response.json(), indent=INDENT_SIZE))
        else:
            print "Request failed with status code: " + str(response.status_code)

    def get_cluster_configuration(self, out_dir):
        response = requests.get(self.url_cluster_configuration)
        if response.status_code == 200:
            file_name = 'cluster-configuration.json'
            full_out_path = os.path.join(out_dir, self.name.lower(), file_name)
            FileWriter().write(full_out_path, json.dumps(response.json(), indent=INDENT_SIZE))
        else:
            print "Request failed with status code: " + str(response.status_code)

    def get_topology_summary(self, out_dir):
        response = requests.get(self.url_topology_summary)
        if response.status_code == 200:
            file_name = 'topology-summary.json'
            full_out_path = os.path.join(out_dir, self.name.lower(), file_name)
            FileWriter().write(full_out_path, json.dumps(response.json(), indent=INDENT_SIZE))
        else:
            print "Request failed with status code: " + str(response.status_code)

    def get_topology_stats_summary(self, out_dir):
        summary_response = requests.get(self.url_topology_summary)
        if summary_response.status_code == 200:
            for feature, value in summary_response.json().iteritems():
                if feature == 'topologies':
                    for topology in value:
                        for k, v in topology.iteritems():
                            if k == 'id':
                                print "Retrieving Storm topology stats summary for topology-id " + v
                                response = requests.get(self.url_topology_stats_summary.format(v))
                                if response.status_code == 200:
                                    file_name = 'topology-{0}-stats-summary.json'.format(v)
                                    full_out_path = os.path.join(out_dir, self.name.lower(), 'stats-summaries', file_name)
                                    FileWriter().write(full_out_path, json.dumps(response.json(), indent=INDENT_SIZE))
                                else:
                                    print "Request failed with status code: " + str(response.status_code)
        else:
            print "Topology listing request failed with status code: " + str(summary_response.status_code)

class KafkaInfo(InfoGatherer):

    def __init__(self, broker_list, zookeeper_quorum, hdp_home):
        super(KafkaInfo, self).__init__('Kafka')
        self.broker_list = broker_list
        self.zookeeper_quorum = zookeeper_quorum
        self.hdp_home = hdp_home

    def collect(self, out_dir):
        print "Retrieving Kafka detail"
        self.get_broker_info(out_dir)
        self.get_kafka_topics(out_dir)
        self.get_topic_detail(out_dir)

    def get_broker_info(self, out_dir):
        print "Retrieving Kafka broker info"
        # note, need to escape the last single quote with the trim command so the string literal works
        broker_id_cmd = '''{0}/kafka-broker/bin/zookeeper-shell.sh {1} <<< "ls /brokers/ids" | grep -e '\[.*\]' | tr -d [] | tr , ' \''''.format(self.hdp_home, self.zookeeper_quorum)
        broker_ids = ShellHandler().ret_output(broker_id_cmd)
        for broker in broker_ids.strip().split(','):
            file_name = 'kafka-broker-{0}-info.txt'.format(broker)
            full_out_path = os.path.join(out_dir, self.name.lower(), 'broker-info', file_name)
            broker_data_cmd = '''echo "get /brokers/ids/{0}" | {1}/kafka-broker/bin/zookeeper-shell.sh {2} 2>&1'''.format(broker, self.hdp_home, self.zookeeper_quorum)
            broker_data = ShellHandler().ret_output(broker_data_cmd)
            FileWriter().write(full_out_path, broker_data)

    def get_kafka_topics(self, out_dir):
        # Get list of Kafka topics
        #echo "Retrieving Kafka topics list"
        #${HDP_HOME}/kafka-broker/bin/kafka-topics.sh --zookeeper $ZOOKEEPER --list >> $KAFKA_DIR/kafka-topics.txt
        pass

    def get_topic_detail(self, out_dir):
        # Get Kafka topic details
        #echo "Retrieving Kafka enrichment topic details"
        #${HDP_HOME}/kafka-broker/bin/kafka-topics.sh --zookeeper $ZOOKEEPER --topic enrichments --describe >> $KAFKA_DIR/kafka-enrichments-topic.txt
        #echo "Retrieving Kafka indexing topic details"
        #${HDP_HOME}/kafka-broker/bin/kafka-topics.sh --zookeeper $ZOOKEEPER --topic indexing --describe >> $KAFKA_DIR/kafka-indexing-topic.txt
        pass

class MetronInfo(InfoGatherer):

    def __init__(self, metron_home, zookeeper_quorum):
        super(MetronInfo, self).__init__('Metron')
        self.metron_home = metron_home
        self.zookeeper_quorum = zookeeper_quorum

    def collect(self, out_dir):
        pass

class HdpInfo(InfoGatherer):

    def __init__(self, hdp_home):
        super(HdpInfo, self).__init__('HDP')
        self.hdp_home = hdp_home

    def collect(self, out_dir):
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
        out_dir = self.get_out_dirname(out_dir_base)
        info_getters = [
                AmbariInfo(ambari_host, cluster_name),
                StormInfo(storm_host),
                KafkaInfo(broker_list, zookeeper_quorum, hdp_home),
                MetronInfo(metron_home, zookeeper_quorum),
                HdpInfo(hdp_home)
        ]
        for getter in info_getters:
            getter.collect(out_dir)
        self.compress_files(out_dir)
        print "Finished gathering debug info"

    # creates dir w/timestamp to drop all configs
    # e.g. metron-debug-2018-03-24_06-50-34
    def get_out_dirname(self, out_dir_base):
        return os.path.join(out_dir_base, 'metron-debug-' + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))

    def compress_files(self, out_dir):
        tarball_name = out_dir + '.tgz'
        print "Creating tarfile bundle with all configs: '{0}'".format(tarball_name)
        with closing(tarfile.open(tarball_name, 'w:gz')) as tar:
            tar.add(out_dir, arcname=os.path.basename(out_dir))
        print "...done"

if __name__ == "__main__":
    ClusterInfo().main()

