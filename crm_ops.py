import os
import sys
import subprocess
import pprint
from xml.dom.minidom import *


class Color:
    """
    A custom fancy colors class
    """
    def __init__(self, fgcode=None, bgcode=None, attrcode=0, enabled=True, brightfg=False, brightbg=False):
        self.start = "\033["
        self.end = "m"
        self.reset = self.start + "0" + self.end

        if enabled:
            self.enabled = True
        else:
            self.enabled = False

        if brightfg:
            self.brightfg = True
        else:
            self.brightfg = False

        if brightbg:
            self.brightbg = True
        else:
            self.brightbg = False

        self.fgoffset = 30
        self.bgoffset = 40
        self.brightoffset = 60

        self.colortable = {
            'black': 0,
            'red': 1,
            'green': 2,
            'yellow': 3,
            'blue': 4,
            'magneta': 5,
            'cyan': 6,
            'white': 7,
            'off': None,
        }

        self.attrtable = {
            'normal': 0,
            'bold': 1,
            'faint': 2,
            #'italic':    3,
            'underline': 4,
            'blink': 5,
            #'rblink':    6,
            'negative': 7,
            'conceal': 8,
            #'crossed':   9,
            'off': 0,
        }

        self.setFG(fgcode)
        self.setBG(bgcode)
        self.setATTR(attrcode)

    def toggle_enabled(self):
        if self.enabled:
            self.enabled = False
        else:
            self.enabled = True

    def toggle_brightfg(self):
        if self.brightfg:
            self.brightfg = False
        else:
            self.brightfg = True

    def toggle_brightbg(self):
        if self.brightbg:
            self.brightbg = False
        else:
            self.brightbg = True

    def setFG(self, color):
        if type(color) == int:
            self.fgcode = color
            return True
        if color in self.colortable:
            self.fgcode = self.colortable[color]
            return True
        self.fgcode = None
        return False

    def setBG(self, color):
        if type(color) == int:
            self.bgcode = color
            return True
        if color in self.colortable:
            self.bgcode = self.colortable[color]
            return True
        self.bgcode = None
        return False

    def setATTR(self, color):
        if type(color) == int:
            self.attrcode = color
            return True
        if color in self.attrtable:
            self.attrcode = self.attrtable[color]
            return True
        self.attrcode = 0
        return False

    def escape(self):
        components = []
        attrcode = self.attrcode

        if self.fgcode is not None:
            fgcode = self.fgoffset + self.fgcode
            if self.brightfg:
                fgcode += self.brightoffset
        else:
            fgcode = None

        if self.bgcode is not None:
            bgcode = self.bgoffset + self.bgcode
            if self.brightbg:
                bgcode += self.brightoffset
        else:
            bgcode = None

        components.append(attrcode)
        if fgcode:
            components.append(fgcode)
        if bgcode:
            components.append(bgcode)

        escstr = self.start + ";".join(map(str, components)) + self.end
        return escstr

    def printchart(self):
        for fg in range(0, 7):
            for bg in range(0, 7):
                for attr in sorted(self.attrtable.values()):
                    democolor = Color(fgcode=fg, bgcode=bg, attrcode=attr, brightfg=False, brightbg=False)
                    sys.stdout.write(democolor("Hello World!"), repr(democolor))
                    democolor.brightfg = True
                    sys.stdout.write(democolor("Hello World!"), repr(democolor))
                    democolor.brightbg = True
                    sys.stdout.write(democolor("Hello World!"), repr(democolor))

    def __str__(self):
        return self.escape()

    def __repr__(self):
        return "Color(fgcode=%d, bgcode=%d, attrcode=%d, enabled=%s, brightfg=%s, brightbg=%s)" % (
            self.fgcode,
            self.bgcode,
            self.attrcode,
            str(self.enabled),
            str(self.brightfg),
            str(self.brightbg),
        )

    def __call__(self, string):
        if self.enabled:
            return self.escape() + string + self.reset
        else:
            return string


class Interface:
    """
    Funcions related to input, output and formattiong of data
    """

    def __init__(self):
        self.debug_level = 0

        self.error_color = Color(fgcode='red')
        self.running_color = Color(fgcode='green', brightfg=True)
        self.not_running_color = Color(fgcode=5, attrcode=0, enabled=True, brightfg=True, brightbg=False)
        self.debug_color = Color(fgcode=6, bgcode=5, attrcode=1, enabled=True, brightfg=False, brightbg=False)
        self.primitive_name_color = Color(fgcode='blue')

        self.ocf_rc_codes = {
            '0': self.running_color('Success'),
            '1': self.error_color('Error: Generic'),
            '2': self.error_color('Error: Arguments'),
            '3': self.error_color('Error: Unimplemented'),
            '4': self.error_color('Error: Permissions'),
            '5': self.error_color('Error: Installation'),
            '6': self.error_color('Error: Configuration'),
            '7': self.not_running_color('Not Running'),
            '8': self.running_color('Master Running'),
            '9': self.error_color('Master Failed'),
        }

    def debug(self, msg='', debug_level=1):
        if self.debug_level >= debug_level:
            sys.stderr.write(str(msg) + "\n")

    def puts(self, msg='', offset=0):
        sys.stdout.write(' ' * offset + str(msg) + "\n")

    def output(self, msg=''):
        sys.stdout.write(str(msg))

    def rc_code_to_string(self, rc_code):
        rc_code = str(rc_code)
        if rc_code in self.ocf_rc_codes:
            return self.ocf_rc_codes[rc_code]
        else:
            return self.error_color('Unknown!')

    def print_resource(self, resource, offset=4):
        resource = resource.copy()
        resource['id'] = self.primitive_name_color(resource['id'])
        line = "> %(id)s (%(class)s::%(provider)s::%(type)s)" % resource
        self.puts(line, offset)

    def print_op(self, op, offset=8):
        op = op.copy()
        op['rc-code-string'] = self.rc_code_to_string(op['rc-code'])
        line = "* %(id)s %(rc-code-string)s" % op
        self.puts(line, offset)

    def print_node(self, node):
        line = "%s\n%s\n%s" % (40 * '=', node, 40 * '=')
        self.puts(line)

    def print_table(self, nodes):
        for node in sorted(nodes):
            self.print_node(node)
            for resource in sorted(nodes[node]):
                self.print_resource(nodes[node][resource])
                for op in nodes[node][resource]['ops']:
                    self.print_op(op)


class CIB:
    """
    Works with CIB xml. Loads it and parses
    """

    def __init__(self):
        self.nodes = {}

    def show_nodes(self):
        printer = pprint.PrettyPrinter(indent=2)
        printer.pprint(self.nodes)

    def get_cib_from_file(self, cib_file=None):
        self.cib_file = cib_file
        self.cib = xml.dom.minidom.parse(self.cib_file)

    def read_cib(self):
        shell = False
        cmd = ['/usr/sbin/cibadmin', '--query']
        
        popen = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
        )

        status_code = popen.wait()
        stdout = popen.stdout
        stderr = popen.stderr

        cib = stdout.read()
        
        if status_code != 0 or len(cib) == 0:
            raise StandardError('Could not get CIB using cibadmin!')
        else:
            self.cib = xml.dom.minidom.parseString(cib)
            return self.cib

    def decode_cib(self):
        if not self.cib:
            raise StandardError('CIB was not got!')

        lrm = self.cib.getElementsByTagName('lrm')

        if len(lrm) == 0:
            raise StandardError('No lrm structures found!')

        for lrm_of_node in lrm:
            if not (lrm_of_node.attributes and lrm_of_node.hasAttribute('id')):
                continue

            node_id = lrm_of_node.attributes['id'].value
            self.nodes[node_id] = {}

            lrm_resources = lrm_of_node.getElementsByTagName('lrm_resource')

            if len(lrm_resources) == 0:
                continue

            for lrm_resource in lrm_resources:
                if not (lrm_resource.attributes and lrm_resource.hasAttribute('id')):
                    continue

                resource = {}
                for lrm_resource_attribute in lrm_resource.attributes.keys():
                    resource[lrm_resource_attribute] = lrm_resource.attributes[lrm_resource_attribute].value

                resource_id = lrm_resource.attributes['id'].value

                ops = []

                lrm_rsc_ops = lrm_resource.getElementsByTagName('lrm_rsc_op')

                if len(lrm_rsc_ops) == 0:
                    continue

                for lrm_rsc_op in lrm_rsc_ops:
                    if not (lrm_rsc_op.attributes and lrm_rsc_op.hasAttribute('id')):
                        continue

                    op = {}
                    for op_attribute in lrm_rsc_op.attributes.keys():
                        op[op_attribute] = lrm_rsc_op.attributes[op_attribute].value

                    ops.append(op)

                ops.sort(key=lambda o: o.get('call_id', '0'))

                resource['role'] = self.determine_resource_role(ops)

                self.nodes[node_id][resource_id] = resource
                self.nodes[node_id][resource_id]['ops'] = ops

    def determine_resource_role(self, ops):
        return 'Started'


cib = CIB()
#cib.read_cib()
cib.get_cib_from_file('cib.xml')
cib.decode_cib()

interface = Interface()
interface.print_table(cib.nodes)