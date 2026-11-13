import hashlib
import os
import time
import bpy

from typing import List, Dict, Union, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from datetime import datetime

from ..addon.settings import WWMI_Settings
from ..migoto_io.blender_interface.utility import *
from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *
from ..migoto_io.blender_interface.mesh import *

from ..migoto_io.data_model.byte_buffer import NumpyBuffer

from ..extract_frame_data.metadata_format import ExtractedObject

from .object_merger import MergedObject, SkeletonType
from .metadata_collector import Version, ModInfo
from .texture_collector import Texture
from .text_formatter import TextFormatter

from ..libs.jinja2 import Template, TemplateSyntaxError, UndefinedError


chached_template: Optional[str] = None
chached_template_string: Optional[Template] = None


@dataclass
class IniMaker:
    # Input
    cfg: WWMI_Settings
    mod_info: ModInfo
    extracted_object: ExtractedObject
    merged_object: MergedObject
    buffers: Dict[str, NumpyBuffer]
    textures: List[Texture]
    comment_code: bool
    unrestricted_custom_shape_keys: bool
    skeleton_scale: float
    formatter: TextFormatter = TextFormatter()
    # Output
    ini_string: str = field(init=False)
    
    def start_live_write(self, context, cfg):
        thread = Thread(target=self.live_write_thread, args=(context, cfg))
        thread.start()

    def live_write_thread(self, context, cfg):
        print('Started live ini updates.')
        
        if cfg.custom_template_source == 'INTERNAL':
            text = bpy.data.texts["CustomIniTemplate"]
            template_string = None
            custom_template_path = None
            mod_time = None
        else:
            custom_template_path = resolve_path(cfg.custom_template_path)
            mod_time = custom_template_path.stat().st_mtime
        
        while True:

            if not cfg.custom_template_live_update:
                print('Stopped live ini updates.')
                return

            if mod_time is None:
                new_template_string = text.as_string()
                template_updated = template_string != new_template_string
                if template_updated:
                    template_string = new_template_string
            else:
                new_mod_time = custom_template_path.stat().st_mtime
                template_updated = mod_time != new_mod_time
                if template_updated:
                    new_template_string = self.get_custom_template(context, cfg)
                    mod_time = new_mod_time

            if template_updated:
                try:
                    result = self.build_from_template(context, cfg, template_string=new_template_string, with_checksum=True)
                except ValueError as e:
                    result = str(e)
                except Exception as e:
                    import traceback
                    result = f'Ini Template error:\n\n{str(e)}\n\n\n{traceback.format_exc()}'

                self.write(ini_string=result)

            time.sleep(0.05)      

    @staticmethod
    def get_default_template(context, cfg, remove_code_comments = False):

        default_templates_path = Path(os.path.realpath(__file__)).parent.parent / 'templates'

        if cfg.mod_skeleton_type == 'MERGED':
            default_template_path = default_templates_path / 'merged.ini.j2'
        elif cfg.mod_skeleton_type == 'COMPONENT':
            default_template_path = default_templates_path / 'per_component.ini.j2'
        else:
            raise ValueError(f'Unknown skeleton type {cfg.mod_skeleton_type}!')

        result = ''

        with open(default_template_path, 'r', encoding='utf-8') as f:
            raw_data = f.read()

            if not remove_code_comments:
                return raw_data

            for line in raw_data.split('\n'):
                if not line.strip().startswith('{{note'):
                    result += line + '\n'

        return result

    @staticmethod
    def get_custom_template(context, cfg):
        if cfg.custom_template_source == 'INTERNAL':
            template_text = bpy.data.texts["CustomIniTemplate"]
            if template_text is not None:
                template = template_text.as_string()
        else:
            template_path = resolve_path(cfg.custom_template_path)
            if not template_path.is_file():
                raise ValueError(f'Custom ini template file not found: `{template_path}`!')
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        return template

    def build_from_template(self, context, cfg, template_string = None, with_checksum = False):
        # Try to load custom template
        if template_string is None and cfg.use_custom_template:
            template_string = self.get_custom_template(context, cfg)
        # Use default template if custom one is not configured or empty
        if template_string is None or not(template_string.strip()):
            template_string = self.get_default_template(context, cfg, remove_code_comments=not cfg.comment_ini)

        global chached_template, chached_template_string
        if chached_template_string is not None and template_string == chached_template_string:
            template = chached_template
        else:
            start_time = time.time()
            try:
                template = Template(template_string)
                chached_template = template
                chached_template_string = template_string
            except TemplateSyntaxError as e:
                template_lines = template_string.split('\n')
                template_fragment = ''
                for i in range(e.lineno-4, e.lineno+2):
                    template_fragment += f'{i}: {template_lines[i]}\n'
                raise ValueError(f'Ini Template syntax error:\n\n'
                                 f'{e.message}\n\n'
                                 f'Line Number: {e.lineno} (actual cause may be located above this line)\n\n'
                                 f'Template Fragment:\n'
                                 f'{template_fragment}')
            print(f'Ini template caching time: {time.time() - start_time :.3f}s')

        try:
            rendered_string = template.render({**vars(self), 'enumerate': enumerate})
        except UndefinedError as e:
                raise ValueError(f'Ini Template filling error:\n'
                                 f'{e}')

        result = ''.join([line + '\n' for line in rendered_string.split('\n') if not line.strip().startswith(';DEL')])

        if with_checksum:
            result = self.with_checksum(result)
        
        self.ini_string = result

        return result

    def write(self, ini_string: str = None, ini_path = None):
        if ini_path is None:
            ini_path = resolve_path(self.cfg.mod_output_folder) / 'mod.ini'
        if ini_string is None:
            ini_string = self.ini_string
        if ini_path.is_file() and self.is_ini_edited(ini_path):
            timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            backup_path = ini_path.with_name(f'{ini_path.name} {timestamp}.BAK')
            print(f'Writing backup {backup_path.name}...')
            ini_path.rename(backup_path)
        with open(ini_path, 'w', encoding='utf-8') as f:
            print(f'Writing {ini_path.name}...')
            f.write(ini_string)  
    
    @staticmethod
    def with_checksum(lines):
        '''
        Calculates sha256 hash of provided lines and adds following looking entry to the end:
        '; SHA256 CHECKSUM: 401cafcfdb224c5013802b3dd5a5442df5f082404a9a1fed91b0f8650d604370' + '\n'
        Allows to detect if mod.ini was manually edited to prevent accidental overwrite
        '''
        lines = lines.strip() + '\n'
        sha256 = hashlib.sha256(lines.encode('utf-8')).hexdigest()
        lines += f'; SHA256 CHECKSUM: {sha256}' + '\n'
        return lines

    @staticmethod
    def is_ini_edited(ini_path):
        '''
        Extracts defined SHA256 CHECKSUM from provided file and calculates sha256 of remaining lines
        If hashes match, it means that file doesn't contain any manual edits
        Allows to detect if mod.ini was manually edited to prevent accidental overwrite
        '''
        with open(ini_path, 'r') as f:
            data = list(f)

            # Extract data from expected location of checksum stamp
            checksum = data[-1].strip()

            # Ensure that checksum stamp has expected prefix 
            checksum_prefix = '; SHA256 CHECKSUM: '
            if not checksum.startswith(checksum_prefix):
                return False
            
            # Extract sha256 hash value from checksum stamp
            sha256 = checksum.replace(checksum_prefix, '')
            
            # Calculate sha256 hash of all lines above checksum stamp
            ini_data = data[:-1]
            ini_sha256 = hashlib.sha256(''.join(ini_data).encode('utf-8')).hexdigest()

            # Check if checksums are matching, different sha256 means data was edited
            if ini_sha256 != sha256:
                return True

            return False
