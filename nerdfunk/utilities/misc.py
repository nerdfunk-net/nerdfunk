from copy import deepcopy
import logging
import yaml


def read_config(filename):
    """
    read config from file
    Returns: json
    """
    with open(filename) as f:
        try:
            return yaml.safe_load(f.read())
        except Exception as exc:
            logging.error("could not parse yaml file %s; exception: %s" % (filename, exc))
            return None

def get_value_from_dict(dictionary, keys):
    if dictionary is None:
        return None

    nested_dict = dictionary

    for key in keys:
        try:
            nested_dict = nested_dict[key]
        except KeyError as e:
            return None
        except IndexError as e:
            return None
        except TypeError as e:
            return nested_dict

    return nested_dict

def modify_dict(datadict, origin):
    """
    modifies dict from config style to specified dict style
    this is needed by the config_context mechanism

    :param datadict:
    :param origin:
    :return: dict
    """

    # deepcopy before data manipulation
    newdict = deepcopy(datadict)
    transformed = False
    PLACEHOLDER = r"^{{(\S+)}}$"

    for key, value in datadict.items():
        # recurse into nested dicts
        if isinstance(value, dict):
            match = re.match(PLACEHOLDER, key)
            if match:
                transformed = True
                new_key = get_value_from_dict(origin, match.group(1).split("."))
                newdict[new_key] = modify_dict(datadict[key], origin)
                del newdict[key]
            else:
                new_key = key
                newdict[new_key] = modify_dict(datadict[key], origin)
        else:
            match = re.match(PLACEHOLDER, value)
            if match:
                transformed = True
                newdict[key] = get_value_from_dict(origin, match.group(1).split("."))

    return newdict

def get_loglevel(level):
    if level == 'debug':
        return logging.DEBUG
    elif level == 'info':
        return logging.INFO
    elif level == 'critical':
        return logging.CRITICAL
    elif level == 'error':
        return logging.ERROR
    else:
        return logging.NOTSET
