import bpy

from textwrap import dedent


class ConfigError(Exception):
    def __init__(self, setting_name, error_message, cfg = None):
        if cfg is None:
            cfg = bpy.context.scene.wwmi_tools_settings
        cfg.last_error_setting_name = setting_name
        error_message = dedent(str(error_message)).strip()
        cfg.last_error_text = error_message
        print('ERROR:', error_message)
        super().__init__(error_message)
        import traceback
        print(traceback.format_exc())


def clear_error(cfg):
    cfg.last_error_setting_name = ''
    cfg.last_error_text = ''
