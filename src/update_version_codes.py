from shotgun_api3 import Shotgun
import re

SERVER_PATH = 'https://iceanimations.shotgunstudio.com'
SCRIPT_NAME = 'TestScript'
SCRIPT_KEY = '446a726a387c5f8372b1b6e6d30e4cd05d022475b51ea82ebe1cff34896cf2f2'

sg = Shotgun(SERVER_PATH, SCRIPT_NAME, SCRIPT_KEY)

code_pattern = re.compile(r'^(EP\d+_SQ\d+_SH\d+)_?V(\d+)$', re.IGNORECASE)
def suggest_new_code(code, pattern=code_pattern):
    match = code_pattern.match(code)
    if match:
        version_number = int(match.group(2))
        if version_number <= 1:
            return
        return match.group(1) + '_animation_preview_' + 'V%03d'%(version_number-1)


def update_version_names():
    project = sg.find_one('Project', [('name', 'contains', 'halfan')])
    if not project:
        raise Exception, 'Project not found'
    all_versions = sg.find('Version', [('project', 'is', project)], ['code'])
    batch_data_list = []

    print 'analyzing', len(all_versions), 'versions ...'

    for version in all_versions:
        replace = suggest_new_code(version['code'])
        if replace:
            batch_data = {}
            batch_data['request_type']='update'
            batch_data['entity_type']='Version'
            batch_data['entity_id']=version['id']
            data = {}
            data['code']=replace
            batch_data['data'] = data
            batch_data_list.append(batch_data)

    print 'versions to be updated', len(batch_data_list)
    print '...'
    sg.batch(batch_data_list)
    print 'done'



if __name__ == '__main__':
    update_version_names()
