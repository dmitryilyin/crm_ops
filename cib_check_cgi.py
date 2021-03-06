#!/usr/bin/env python
import cgi
import subprocess
import pprint
import sys
import platform
from xml.dom.minidom import *


class CGIinterface:
    def __init__(self):
        self.request = cgi.FieldStorage()
        self.hostname = self.request.getfirst('hostname', None)
        self.resource = self.request.getfirst('resource', None)

        if not self.hostname:
            self.hostname = platform.node()

        if not self.hostname:
            self.send_cgi(400, 'No hostname sent')

        if not self.resource:
            self.send_cgi(400, 'No resource sent')

        self.create_cib()
        self.cib.decode_lrm()

        if not self.hostname in self.cib.nodes:
            self.send_cgi(404, 'Node "%s" was not found' % self.hostname)
        node = self.cib.nodes[self.hostname]

        if not self.resource in node['resources']:
            self.send_cgi(404, 'Resource "%s" was not found on node "%s"' % (self.resource, self.hostname))

        resource = node['resources'][self.resource]
        ops = resource['ops']

        status = self.cib.determine_resource_status(ops)

        if status in ['start', 'promote']:
            code = 200
        else:
            code = 503

        self.send_cgi(code, 'Resource "%s" on node "%s" has status "%s"' % (self.resource, self.hostname, status))

    def send_cgi(self, code='200', msg='OK'):
        data = ''
        data += "Status: %d %s\r\n" % (code, msg)
        data += "Content-type:text/html\r\n\r\n"
        data += "<html>%s</html>\r\n" % msg
        sys.stdout.write(data)
        sys.exit(0)

    def create_cib(self):
        try:
            self.cib = CIB(self)
            #self.cib.get_cib_from_pacemaker()
            self.cib.get_cib_from_file('cib.xml')
        except:
            self.send_cgi(500, 'Could not get CIB')

    def debug(self, msg='', debug=1, offset=None):
        pass


class CIB:
    """
    Works with CIB xml. Loads it and parses
    """

    def __init__(self, interface):
        self.nodes = {}
        self.interface = interface

    def show_nodes(self):
        """
        Return pretty printed node structure for debug purpose
        @return: Pretty-printed nodes structure
        """
        printer = pprint.PrettyPrinter(indent=2)
        return printer.pformat(self.nodes)

    def __str__(self):
        return self.xml

    def __repr__(self):
        self.show_nodes()

    def get_cib_from_file(self, cib_file=None):
        """
        Get cib XML DOM structure by reading xml file
        @param cib_file: Path to file (cibadmin -Q > cib.xml)
        @return: XML document
        """
        self.cib_file = cib_file
        self.xml = xml.dom.minidom.parse(self.cib_file)
        if not self.xml:
            raise StandardError('Could not get CIB from file!')
        return self.xml

    def get_cib_from_pacemaker(self):
        """
        Get cib XML DOM from Pacemaker by calling cibadmin
        @return: XML document
        """
        shell = False
        cmd = ['/usr/sbin/cibadmin', '--query']
        exception = 'Could not get CIB using cibadmin!'

        try:
            popen = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
            )

            status_code = popen.wait()
            stdout = popen.stdout
            #stderr = popen.stderr

            cib = stdout.read()
        except:
            raise StandardError(exception)
        if status_code != 0 or len(cib) == 0:
            raise StandardError(exception)
        else:
            self.xml = xml.dom.minidom.parseString(cib)
        if not self.xml:
            raise StandardError('Could not get CIB from pacemaker!')
        return self.xml

    def decode_lrm_op(self, lrm_op_block):
        """
        Decode operation block of lrm section
        @param lrm_op_block: Op block of the XML document
        @return: Operation structure
        """
        op = {}
        for op_attribute in lrm_op_block.attributes.keys():
            op[op_attribute] = lrm_op_block.attributes[op_attribute].value
        return op

    def decode_lrm_resource(self, lrm_resource_block):
        """
        Decode resource block of lrm section
        @param lrm_resource_block: Resource block of the XML document
        @return: Resource structure
        """
        resource = {}

        for lrm_resource_attribute in lrm_resource_block.attributes.keys():
            resource[lrm_resource_attribute] = lrm_resource_block.attributes[lrm_resource_attribute].value
        resource['ops'] = []

        lrm_rsc_ops = lrm_resource_block.getElementsByTagName('lrm_rsc_op')

        for lrm_of_single_op in lrm_rsc_ops:
            if not (lrm_of_single_op.attributes and lrm_of_single_op.hasAttribute('id')):
                continue
            op = self.decode_lrm_op(lrm_of_single_op)
            self.interface.debug('Op: %s' % op['id'], 2, 3)
            resource['ops'].append(op)

        resource['ops'].sort(key=lambda o: o.get('call-id', '0'))
        resource['status'] = self.determine_resource_status(resource['ops'])

        return resource

    def decode_lrm_node(self, lrm_node_block):
        """
        Decode node block of lrm section
        @param lrm_node_block: Node block of the XML document
        @return: Node structure
        """
        node_data = {}

        node_id = lrm_node_block.attributes['id'].value
        node_data['id'] = node_id
        node_data['resources'] = {}

        lrm_of_all_resources = lrm_node_block.getElementsByTagName('lrm_resource')

        for lrm_of_single_resource in lrm_of_all_resources:
            if not (lrm_of_single_resource.attributes and lrm_of_single_resource.hasAttribute('id')):
                continue
            resource_id = lrm_of_single_resource.attributes['id'].value
            resource_data = self.decode_lrm_resource(lrm_of_single_resource)
            self.interface.debug('Resource: %s' % resource_id, 2, 2)
            node_data['resources'][resource_id] = resource_data

        return node_data

    def decode_lrm(self):
        """
        Find lrm sections and decode them
        @return: Nodes structure
        """
        lrm_of_all_nodes = self.xml.getElementsByTagName('lrm')
        if len(lrm_of_all_nodes) == 0:
            return None

        for lrm_of_single_node in lrm_of_all_nodes:
            if not (lrm_of_single_node.attributes and lrm_of_single_node.hasAttribute('id')):
                continue
            node_id = lrm_of_single_node.attributes['id'].value
            node_data = self.decode_lrm_node(lrm_of_single_node)
            self.interface.debug('Node: %s' % node_id, 2, 1)
            self.nodes[node_id] = node_data
        return self.nodes

    def determine_resource_status(self, ops):
        """
        Determite the status of a resource by analyzing
        last lrm operations.
        @param ops: Operations array
        @return: Resource status string
        """
        last_op = None

        for op in ops:
            self.interface.debug('Status Op: %s' % op, 3, 3)
            # skip incomplite ops
            if not op.get('op-status', None) == '0':
                continue

            # skip useless operations
            if not op.get('operation', None) in ['start', 'stop', 'monitor', 'promote']:
                continue

            # skip unsuccessfull operations
            if not (op.get('rc-code', None) == '0' or op.get('operation', None) == 'monitor'):
                continue

            last_op = op

        if not last_op:
            return '?'

        if last_op.get('operation', None) in ['promote', 'start', 'stop']:
            status = last_op['operation']
        elif last_op.get('rc-code', None) in ['0', '8']:
            status = 'start'
        else:
            status = 'stop'

        self.interface.debug('Status: %s' % status, 3, 3)
        return status

###########################################################################################################

if __name__ == '__main__':
    interface = CGIinterface()

