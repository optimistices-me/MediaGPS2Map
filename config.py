import json


def load_config(config_file='config.json'):
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    config['directories'] = [directory.replace('\\', '/') for directory in config['directories']]
    return config
