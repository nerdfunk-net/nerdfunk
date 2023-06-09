import logging
import glob
import os
import yaml
import textfsm
import sys
from scrapli import Scrapli


def get_loglevel(level):
    if level == 'debug':
        return logging.DEBUG
    elif level == 'info':
        return logging.INFO
    elif level == 'critical':
        return logging.CRITICAL
    elif level == 'error':
        return logging.ERROR
    elif level == 'none':
        return 100
    else:
        return logging.NOTSET


class Devicemanagement:

    def __init__(self, **kwargs):
        self.__ip_address = None
        self.__platform = None
        self.__manufacturer = None
        self.__username = None
        self.__password = None
        self.__port = 22
        self.__connection = None

        if 'ip' in kwargs:
            self.__ip_address = kwargs['ip']
        if 'platform' in kwargs:
            self.__platform = kwargs['platform']
        if 'username' in kwargs:
            self.__username = kwargs['username']
        if 'password' in kwargs:
            self.__password = kwargs['password']
        if 'port' in kwargs:
            self.__port = kwargs['port']
        if 'manufacturer' in kwargs:
            self.__manufacturer = kwargs['manufacturer']
        if 'scrapli_loglevel' in kwargs:
            if kwargs['scrapli_loglevel']:
                logging.getLogger('scrapli').setLevel(get_loglevel(kwargs['scrapli_loglevel']))
                logging.getLogger('scrapli').propagate = True
            else:
                logging.getLogger('scrapli').setLevel(logging.ERROR)
                logging.getLogger('scrapli').propagate = False

    def open(self):

        # we have to map the driver to our srapli driver / platform
        #
        # napalm | scrapli
        # -------|------------
        # ios    | cisco_iosxe
        # iosxr  | cisco_iosxr
        # nxos   | cisco_nxos

        mapping = {'ios': 'cisco_iosxe',
                   'iosxr': 'cisco_iosxr',
                   'nxos': 'cisco_nxos'
                   }
        driver = mapping.get(self.__platform)
        if driver is None:
            return False

        device = {
            "host": self.__ip_address,
            "auth_username": self.__username,
            "auth_password": self.__password,
            "auth_strict_key": False,
            "platform": driver,
            "port": self.__port,
            "ssh_config_file": "~/.ssh/ssh_config"
        }

        self.__connection = Scrapli(**device)
        logging.debug("opening connection to device (%s)" % self.__ip_address)
        try:
            self.__connection.open()
        except Exception as exc:
            logging.error(f'could not connect to {self.__ip_address}')
            return False

        return True

    def close(self):
        logging.debug("closing connection to device (%s)" % self.__ip_address)
        try:
            self.__connection.close()
        except:
            logging.error('connection was not open')

    def get_config(self, configtype):
        logging.debug("send show %s to device (%s)" % (configtype, self.__ip_address))
        if not self.__connection:
                if not self.open():
                    return None
        response = self.__connection.send_command("show %s" % configtype)
        return response.result

    def send_and_parse_command(self, commands):
        BASEDIR = os.path.abspath(os.path.dirname(__file__))
        directory = os.path.join(BASEDIR, './conf/textfsm')
        result = {}
        mapped = {}

        for cmd in commands:
            command = cmd["command"]["cmd"]
            logging.debug("sending command %s" % command)
            if not self.__connection:
                if not self.open():
                    return None
            try:
                response = self.__connection.send_command(command)
            except Exception as exc:
                logging.error("could not send command %s to device; got exception %s" % (command, exc))
                return None 

            filename = cmd["command"]["template"].get(self.__platform)
            logging.debug("filename is %s" % filename)
            if filename is None:
                logging.error("no template for platform %s configured" % self.__platform)
                result[command] = {}

            if not os.path.isfile("%s/%s" % (directory, filename)):
                logging.error("template %s does not exists" % filename)
                result[command] = {}

            try:
                logging.debug("reading template")
                template = open("%s/%s" % (directory, filename))
                re_table = textfsm.TextFSM(template)
                logging.debug("parsing response")
                fsm_results = re_table.ParseText(response.result)
                collection_of_results = [dict(zip(re_table.header, pr)) for pr in fsm_results]
                result[command] = collection_of_results
            except Exception as exc:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logging.error("parser error in line %s; got: %s (%s, %s, %s)" % (exc_tb.tb_lineno,
                                                                                 exc,
                                                                                 exc_type,
                                                                                 exc_obj,
                                                                                 exc_tb))
                result[command] = {}

            # check if we have a mapping
            # print(json.dumps(result, indent=4))
            if 'mapping' in cmd["command"]:
                logging.debug("mapping is enabled")
                if command not in mapped:
                    mapped[command] = []
                for res in result[command]:
                    m = {}
                    for key, value in res.items():
                        is_mapped = False
                        for map in cmd["command"]['mapping']:
                            if key == map["src"]:
                                m[map["dst"]] = value
                                is_mapped = True
                        if not is_mapped:
                            m[key] = value
                    mapped[command].append(m)
                result = mapped

        return result

    def get_facts(self):
        BASEDIR = os.path.abspath(os.path.dirname(__file__))
        directory = os.path.join(BASEDIR, './conf/facts')
        files = []
        facts = {}
        values = {}

        # read all facts from config
        for filename in glob.glob(os.path.join(directory, "*.yaml")):
            with open(filename) as f:
                logging.debug("opening file %s to read facts config" % filename)
                try:
                    config = yaml.safe_load(f.read())
                    if config is None:
                        logging.error("could not parse file %s" % filename)
                        continue
                except Exception as exc:
                    logging.error("could not read file %s; got exception %s" % (filename, exc))
                    continue

                active = config.get('active')
                name = config.get('name')
                if not active:
                    logging.debug("config context %s in %s is not active" % (name, filename))
                    continue

                file_vendor = config.get("vendor")
                if file_vendor is None or file_vendor != self.__manufacturer:
                    logging.debug("skipping file %s (%s)" % (filename, file_vendor))
                    continue

                files.append(os.path.basename(filename))
                values = self.send_and_parse_command(config['facts'])
                if values is None:
                    return None
                # print(json.dumps(values, indent=4))

        facts["manufacturer"] = self.__manufacturer
        if "show version" in values:
            facts["os_version"] = values["show version"][0].get("VERSION",None)
            if facts["os_version"] is None:
                # nxos uses OS instead of version
                facts["os_version"] = values["show version"][0].get('OS', 'unknown')
            facts["software_image"] = values["show version"][0].get("SOFTWARE_IMAGE", None)
            if facts["software_image"] is None:
                # nxos uses BOOT_IMAGE instead of SOFTWARE_IMAGE
                facts["software_image"] = values["show version"][0].get("BOOT_IMAGE",'unknown')
            facts["serial_number"] = values["show version"][0]["SERIAL"]
            if 'HARDWARE' in values["show version"][0]:
                facts["model"] = values["show version"][0]["HARDWARE"][0]
            else:
                # nxos uses PLATFORM instead of HARDWARE
                model = values["show version"][0].get('PLATFORM',None)
                if model is None:
                    facts["model"] = "default_type"
                else:
                    facts["model"] = "nexus-%s" % model
            facts["hostname"] = values["show version"][0]["HOSTNAME"]

        if "show hosts" in values and len(values["show hosts"]) > 0:
            facts["fqdn"] = "%s.%s" % (facts.get("hostname"), values["show hosts"][0]["DEFAULT_DOMAIN"])
        else:
            facts["fqdn"] = facts.get("hostname")

        logging.debug("processed %s to get facts of device" % files)
        # print(json.dumps(facts, indent=4))

        return facts
