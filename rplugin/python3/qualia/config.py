from os import environ
from pathlib import Path

from appdirs import user_data_dir, user_config_dir

from qualia.utils.config_utils import create_directory_if_absent, force_remove_directory

FIREBASE_WEB_APP_CONFIG = {
    # On https://console.firebase.google.com (free plan),
    # Go to Project Settings -> Add app -> "</>" (web app option)
    # Set name -> Continue -> Use the displayed "firebaseConfig"
    "apiKey": "AIzaSyDFNIazv7K0qDDJriiYPbhmB3OzUJYJvMI",
    "authDomain": "qualia-321013.firebaseapp.com",
    "databaseURL": "https://qualia-321013-default-rtdb.firebaseio.com",
    "projectId": "qualia-321013",
    "storageBucket": "qualia-321013.appspot.com",
    "messagingSenderId": "707949243379",
    "appId": "1:707949243379:web:db239176c6738dc5578086",
    "measurementId": "G-BPNP22GS5X"
}

_GIT_TOKEN = 'ghp_QJSHBmXvDAbjiiI' 'BHTDEb3yryLofv52dcTbP'
_GIT_REPOSITORY = "github.com/tejasvi8874/test"
GIT_AUTHORIZED_REMOTE = f"https://{_GIT_TOKEN}{'@' if _GIT_TOKEN else ''}{_GIT_REPOSITORY}"
GIT_SEARCH_URL = f"https://{_GIT_REPOSITORY}/search?q="
GIT_BRANCH = "main"

NEST_LEVEL_SPACES = 4

DEBUG = True
NVIM_DEBUG_PIPE = r'\\.\pipe\nvim-15600-0'  # E.g. nvim --listen \\.\pipe\nvim-15600-0 test.md

QUALIA_DATA_DIR = user_data_dir("qualia")
QUALIA_CONFIG_DIR = user_config_dir('qualia')

# Adds delay
ENCRYPT_DB = True
ENCRYPT_NEW_GIT_REPOSITORY = True
ENCRYPT_REALTIME = True

OVERRIDE_ADVANCED_SETTINGS = False

if "QUALIA_CONFIG" in environ:
    qualia_env_config_file = environ["QUALIA_CONFIG"]
    if qualia_env_config_file != 'NONE':
        exec(Path(qualia_env_config_file).read_text())
else:
    config_file = Path(QUALIA_CONFIG_DIR).joinpath("config.py")
    if config_file.is_file():
        exec(config_file.read_text())

# Internal constants

if DEBUG:
    QUALIA_DATA_DIR += '_debug'
    QUALIA_CONFIG_DIR += '_debug'

if not OVERRIDE_ADVANCED_SETTINGS:
    _SHORT_BUFFER_ID = True  # not DEBUG
    _SORT_SIBLINGS = False

    _EXPANDED_BULLET = '-'
    _TO_EXPAND_BULLET = '*'
    _COLLAPSED_BULLET = '+'
    _FZF_LINE_DELIMITER = "\t"
    _TRANSPOSED_FILE_PREFIX = "~"
    _CONFLICT_MARKER = "__ミ๏ｖ๏彡__"

    _APP_CONFIG_PATH = Path(QUALIA_CONFIG_DIR)
    create_directory_if_absent(_APP_CONFIG_PATH)

    _APP_DATA_PATH = Path(QUALIA_DATA_DIR)

    _FILE_FOLDER = _APP_DATA_PATH.joinpath("files")
    _DB_FOLDER = _APP_DATA_PATH.joinpath("db")
    _GIT_FOLDER = _APP_DATA_PATH.joinpath("git")
    _LOG_FOLDER = _APP_DATA_PATH.joinpath('logs')
    _LOG_FILENAME = _LOG_FOLDER.joinpath('logs.txt')

    # Before starting resets data in QUALIA_DATA_DIR (DEBUG adds '_debug' to the path by default)
    _RESET_APP_FOLDER = False

    for _path in (_FILE_FOLDER, _GIT_FOLDER, _DB_FOLDER, _LOG_FOLDER):
        if _RESET_APP_FOLDER:
            force_remove_directory(_path)
        create_directory_if_absent(_path)

    _ROOT_ID_KEY = "root_id"
    _CLIENT_KEY = "client"
    _DB_ENCRYPTION_ENABLED_KEY = "encryption_enabled"

    _LOGGER_NAME = "qualia"
    _BACKUP_COUNT = 10
    _BACKUP_DAYS_INTERVAL = 1

    if "GOOGLE_APPLICATION_CREDENTIALS" not in environ:
        environ["GOOGLE_APPLICATION_CREDENTIALS"] = _APP_CONFIG_PATH.joinpath('firebase-adminsdk.json').as_posix()

    _ENCRYPTION_KEY_FILE = _APP_CONFIG_PATH.joinpath('qualia_secret.key')
    _ENCRYPTION_USED = ENCRYPT_DB or ENCRYPT_REALTIME or ENCRYPT_NEW_GIT_REPOSITORY
    if _ENCRYPTION_USED and not _ENCRYPTION_KEY_FILE.exists():
        from cryptography.fernet import Fernet

        _ENCRYPTION_KEY_FILE.write_bytes(Fernet.generate_key())
    _GIT_ENCRYPTION_ENABLED_FILE_NAME = '.encryption_enabled'
    _GIT_ENCRYPTION_DISABLED_FILE_NAME = '.encryption_disabled'
_PREVIEW_NEST_LEVEL = 1
_SHORT_ID_STORE_BYTES = 6
