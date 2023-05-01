from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from nerdfunk.utilities import misc as misc
import getpass
import os
import base64
import logging


def get_username_and_password(profile, profile_config, password=None):
    """
    get username and password from profile
    Args:
        profile:
        profile_config:
        password:

    Returns:
        username: str
        password: str
    """
    username = None

    if profile is not None:
        logging.debug("using profile %s" % profile)
        account = get_profile(profile_config, profile)
        if not account['success']:
            logging.error("could not retrieve username and password")
        else:
            username = account.get('username')
            password = account.get('password')
    if username is None:
        username = input("Username (%s): " % getpass.getuser())
        if username == "":
            username = getpass.getuser()
    if password is None:
        password = getpass.getpass(prompt="Enter password for %s: " % username)

    logging.debug("username=%s, password=***" % username)

    return username, password


def decrypt_password(password):
    """

    decrypts base64 password that is stored in our yaml config

    Args:
        password:

    Returns: clear password

    """
    # prepare salt
    salt_ascii = os.getenv('SALT')
    salt_bytes = str.encode(salt_ascii)

    # prepare encryption key, we need it as bytes
    encryption_key_ascii = os.getenv('ENCRYPTIONKEY')
    encryption_key_bytes = str.encode(encryption_key_ascii)

    # get password as base64 and convert it to bytes
    password_bytes = base64.b64decode(password)

    # derive key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        iterations=390000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(encryption_key_bytes))

    f = Fernet(key)
    # decrypt and return
    try:
        return f.decrypt(password_bytes).decode("utf-8")
    except:
        return None


def get_profile(config, profilename='default'):
    """
        gets profile (username and password) from config
    Args:
        config:
        profilename:

    Returns: account as dict

    """

    result = {}
    clear_password = None

    username = misc.get_value_from_dict(config, ['accounts', 'devices', profilename, 'username'])
    password = misc.get_value_from_dict(config, ['accounts', 'devices', profilename, 'password'])

    if password is not None:
        clear_password = decrypt_password(password)

    if clear_password is None:
        return {'success': False, 'reason': 'wrong password'}
    else:
        return {'success': True, 'username': username, 'password': clear_password}

