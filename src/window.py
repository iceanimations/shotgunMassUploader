'''
Created on Jul 11, 2015

@author: iqra.idrees
'''
import sip
from __builtin__ import True
#from wsgiref.validate import check_input
sip.setapi('QString', 2)
from PyQt4.QtGui import QApplication, QTableWidget, QTableWidgetItem, QMessageBox
from PyQt4 import uic, QtCore
from PyQt4.QtCore import Qt
import sys
import os
from shotgun_api3 import Shotgun
import os.path as osp
import hashlib
import getpass
import re
import traceback

sys.path.insert(0, "R:\\Pipe_Repo\\Users\\Iqra\\modules")
sys.path.append("R:\\Pipe_Repo\\Users\\Qurban\\utilities")
import cui
import msgBox

SERVER_PATH = 'https://iceanimations.shotgunstudio.com'
SCRIPT_NAME = 'TestScript'
SCRIPT_KEY = '446a726a387c5f8372b1b6e6d30e4cd05d022475b51ea82ebe1cff34896cf2f2'
#PROXY = '10.10.0.212:8080'
PROXY = 'iqra.idrees:padela123@10.10.2.124:8080'
PROXY= None
sg= Shotgun(SERVER_PATH, SCRIPT_NAME, SCRIPT_KEY, http_proxy=PROXY)
user= getpass.getuser()
artist= sg.find_one("HumanUser", [['name', 'is', "ICE Animations"]], ['name'])


rootPath = osp.dirname(osp.dirname(__file__))
filePath= osp.join(rootPath, 'files\project_file.txt')
class PathResolver(object):
    ''' All the local Paths are resolved in this class '''
    project = None
    episode = None
    sequence = None
    shot = None

    def __init__(self, project=None, episode=None, sequence=None, shot=None):
        self.project = project
        self.episode = episode
        self.sequence = sequence
        self.shot = shot

    @property
    def _initialPath(self):
        p_name = self.project
        with open(filePath) as f:
            all_projects = f.readlines()
        #print all_projects
        for i in range(0, len(all_projects)):
            split=all_projects[i].split("=")
            if split[0].rstrip('\n')==p_name:
                return split[1].rstrip('\n')

    @property
    def projectPath(self):
        projName = self.project
        if projName is None:
            raise Exception, 'No project specified'
        return self._initialPath

    @property
    def episodePath(self):
        epName = self.episode
        if epName is None:
            raise Exception, 'No Episode specified'
        if epName == 'No Episode' :
            return self.projectPath
        else:
            return os.path.join(self.projectPath, epName)

    @property
    def sequencePath(self):
        seqname = self.sequence
        if seqname is None:
            raise Exception, 'No sequence specified'
        return os.path.join(self.episodePath, 'SEQUENCES', seqname)

    @property
    def shotPath(self):
        shotName = self.shot
        if shotName is None:
            raise Exception, 'No Shot specified'
        return os.path.join(self.sequencePath, 'SHOTS', shotName )

    @property
    def animationPath(self):
        return os.path.join(self.shotPath, 'animation', 'preview',
                self.episode + '_' + self.shot + '.mov')

    @property
    def animaticPath(self):
        return os.path.join(self.shotPath, 'animatic', self.episode + '_' +
                self.shot + '_animatic.mov')

    @property
    def compPath(self):
        return os.path.join(self.shotPath, 'comp', 'preview', self.episode
                + '_' + self.shot + '.mov')

    episode_re = re.compile(r'^ep\d+', re.I)
    @property
    def episodes(self):
        basePath = self.projectPath
        if os.path.exists(basePath):
            return [name.upper() for name in os.listdir(basePath) if
                    os.path.isdir(os.path.join(basePath, name)) and
                        self.episode_re.match(name)]
        return None

    sequence_re = re.compile(r'^sq\d+', re.I)
    @property
    def sequences(self):
        basePath = os.path.join(self.episodePath, 'SEQUENCES')
        if os.path.exists(basePath):
            return [name.upper() for name in os.listdir(basePath) if
                    os.path.isdir(os.path.join(basePath, name)) and
                        self.sequence_re.match(name)]
        return []

    shot_re = re.compile('^sq\d+_sh\d+', re.I)
    @property
    def shots(self):
        basePath = os.path.join(self.sequencePath, 'SHOTS')
        if os.path.exists(basePath):
            return [name.upper() for name in os.listdir(basePath) if
                    os.path.isdir(os.path.join(basePath, name)) and
                        self.shot_re.match(name)]
        return None

def create_hash(path, blocksize=2**20):
    m = hashlib.md5()
    with open( path , "rb" ) as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update( buf )
    return m.hexdigest()

uiPath = osp.join(rootPath, 'ui')
Form, Base = uic.loadUiType(osp.join(uiPath, 'main.ui'))
class MainWindow(Form, Base):
    defaultProject = '--Select Project--'
    defaultEpisode = '--Select Episode--'
    defaultSequence = '--Select Sequence--'

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.data_list = [] #list of dictionaries to store create version entry stuff
        self.versions=[] #list of dictionaries to store all the upload stuff
        self.paths = PathResolver()
        self.current_proj=0
        self.table = Table(self)
        self.table.setWindowTitle("My Table")
        self.thread= WorkThread(self) #upload thread
        self.multiSelectDropDrown = cui.MultiSelectComboBox(self)
        self.verticalLayout.insertWidget(3, self.multiSelectDropDrown, )


        #initial setup. List of projects in drop down menu
        projects= sg.find("Project",[],['id', 'name']) #finding all projects
        for i in range(0, len(projects)):
            self.selectProject.addItem(projects[i]['name']) #filling DD from shotgun projects


        self.selectProject.activated[str].connect(self.ProjActivated) #filling episodes DD
        self.selectEpi.activated[str].connect(self.EpiActivated) #filling sequences DD
        self.selectSeq.activated[str].connect(self.SeqActivated) #filling shots DD
        self.addshot_button.clicked.connect(self.AddShotActivated) #saving selected shot info to data_list (list)

    def showMessage(self, **kwargs):
        return msgBox.showMessage(self, 'SG Mass Uploader', **kwargs)

    def getProjectName(self):
        return self.selectProject.currentText()

    def getEpName(self):
        return self.selectEpi.currentText()

    def getSeqName(self):
        return self.selectSeq.currentText()

    def getSelectedShotNames(self):
        shots = self.multiSelectDropDrown.getSelectedItems()
        if shots and shots[0] == 'All':
            return self.multiSelectDropDrown.getItems()[1:]
        else:
            return shots

    def process_user_input(self):
        self.table.upload_button.setEnabled(False)
        self.addshot_button.setEnabled(False)
        self.table.progress_label.setText("Please wait. Creating links...Processing...")
        QApplication.processEvents()

        rows= self.table.MyTable.rowCount()
        try:
            for i in range (0, rows): #iterating each row to getting details

                project_name= self.table.MyTable.item(i, 0).text()
                episode_name= self.table.MyTable.item(i, 1).text()
                if episode_name=="None":
                    episode_name=""
                seq_name= self.table.MyTable.item(i, 2).text()
                shot_name= self.table.MyTable.item(i, 3).text()
                shot_type= self.table.MyTable.item(i, 4).text()
                print project_name, episode_name, seq_name, shot_name

                #PROJ DETAILS
                project = sg.find_one("Project",[['name','is',project_name]],['id', 'name'])

                #EPI DETAILS
                if episode_name!="No Episode":
                    episode = sg.find_one("CustomEntity01",[['code','is',episode_name], ['project', 'is', project]],['id', 'code'])
                    if not episode:
                        episode=self.create_episode(project, episode_name)
                        print "epi made"
                else:
                    episode= []

                #SEQ DETAILS
                seq= sg.find_one("Sequence",[['code','is',seq_name],['project', 'is', project]],['id', 'code'])

                if not seq:
                    seq= self.create_sequence(project, episode, seq_name)
                    print "seq made"

                #SHOT DETAILS
                shot= sg.find_one("Shot",[['code','is',shot_name], ['project', 'is', project], ['sg_sequence', 'is', seq]],['id', 'code'])
                if not shot:
                    shot=self.create_shot(project,shot_name, seq) #create new shot
                    print "shot made"

                version_code_postfix = ''

                print seq_name.split('_')[1:]

                paths = PathResolver(project_name, episode_name,
                        '_'.join( seq_name.split('_')[1:] ),
                        '_'.join( shot_name.split('_')[1:] ))

                if shot_type == "Animation":
                    version_code_postfix = '_'.join(['animation', 'preview'])
                    file_path = paths.animationPath

                elif shot_type == 'Animatic':
                    version_code_postfix = 'animatic'
                    file_path = paths.animaticPath

                elif shot_type == 'Comp':
                    version_code_postfix = '_'.join(['comp', 'preview'])
                    file_path = paths.compPath

                version_filters = []
                version_filters.append(('project', 'is', project))
                version_filters.append(('entity', 'is', shot))
                version_filters.append(('code', 'contains',
                    version_code_postfix))

                if not osp.exists(file_path):
                    continue
                file_hash = create_hash(file_path)

                all_versions = sg.find('Version', version_filters, ['code',
                    'sg_hash', 'created_at'])

                already_uploaded, max_version, version_number = False, None, 1

                if all_versions:
                    already_uploaded = any([version['sg_hash']==file_hash for version
                        in all_versions])
                    max_version = max(all_versions, key=self.get_version_number)

                if max_version:
                    version_number = self.get_version_number(max_version) + 1

                if version_number <= 0:
                    version_number = 1
                version_string = 'V%03d'%version_number 

                if already_uploaded:
                    self.table.MyTable.setItem(i , 5, QTableWidgetItem("Version already exists"))
                    self.table.setColour(i, "red")
                    QApplication.processEvents()
                else:
                    # Queue for uploading
                    new_version = {
                            'proj_id': project['id'],
                            'shot_code': shot['code'],
                            'shot_id': shot['id'],
                            'path': file_path,
                            'hash': file_hash,
                            'type': shot_type,
                            'max_version': max_version,
                            'version_code': '_'.join([shot['code'],
                                version_code_postfix, version_string]) }
                    self.data_list.append(new_version)

            self.create_versions()
        except Exception as ex:
            msg = str(ex)
            msg += '\n'
            msg += traceback.format_exc()
            self.showMessage(msg=msg, icon=QMessageBox.Warning)

    versionNumPattern = re.compile(r'.*[vV](\d+)$')
    def get_version_number(self, item, pattern=versionNumPattern):
        if not isinstance(pattern, type(self.versionNumPattern)):
            pattern = re.compile(pattern)
        if isinstance(item, dict):
            item = item['code']
        match = self.versionNumPattern.match(item)
        if match:
            return int(match.group(1))
        return -1

    def create_versions(self):
        self.table.progress_label.setText("")
        batch_data=[]
        all_data= self.data_list
        for item in all_data:

            last_version_number= self.get_latest_version(item) +1
            #print"latest",  last_version_number

            data = {
                'project': {'type':'Project', 'id':item['proj_id']},
                'code': item['version_code'],
                'entity': {'type':'Shot', 'id': item['shot_id']},
                'user': artist,
                'created_by': artist
            }

            batch_data.append({"request_type":"create","entity_type":"Version","data":data} )

        print "BATCH DATA:", batch_data

        created_versions= sg.batch(batch_data) #creating all versions in a batch

        for ver, data in zip(created_versions, all_data):
            one_upload= { 'id': ver['id'], 'hash': data['hash'], 'path': data['path'], 'shot_code': data['shot_code'], 'type': data['type'] }
            self.versions.append(one_upload)

        print "versions to be uploaded:", self.versions


        total=str(len(self.versions))
        count = 2
        intial_prog = "1 of " + total + " uploading "
        self.table.progress_label.setText(intial_prog)
        self.data_list=[] #empty the data list

        #uploading part
        for ver in self.versions:
            print "uploading", ver
            if sg.upload('Version', ver['id'], ver['path'],'sg_uploaded_movie'): #upload new version shot/animatic using new vid
                c= str(count)
                my_progress= c + " of " + total +  " uploading..."
                self.table.progress_label.setText(my_progress)
                sg.update("Version", ver['id'],{'sg_hash': ver['hash']} )

                rows= self.table.MyTable.findItems(ver['shot_code'], Qt.MatchExactly)
                x=0
                if len(rows)==1:
                    x= self.table.MyTable.row(rows[0])
                else:
                    for r in range(0, len(rows)):
                            c_row= self.table.MyTable.row(rows[r])
                            if self.table.MyTable.item(c_row, 4).text()== ver['type']:
                                x= c_row
                                break


                self.table.MyTable.setItem(x , 5, QTableWidgetItem("Uploaded!"))
                self.table.setColour(x, "green")
                QApplication.processEvents()

                print "Upload done"
                count= count + 1

        self.versions=[] #empty uploading list
        p= total + " of " + total +  " uploaded!"
        self.table.progress_label.setText(p)
        self.table.upload_button.setEnabled(True)
        self.addshot_button.setEnabled(True)
        QApplication.processEvents()

    def create_episode(self, project, episode_name):
        data = {
        'project': {'type':'Project','id':project['id']},
        'code': episode_name,
        'description': 'EP blah',
        }

        epi = sg.create("CustomEntity01", data)
        return epi #get epi id of the new episode

    def create_sequence(self, project, episode, seq_name):
        if self.getEpName()!='No Episode':

            data = {
            'project': {'type':'Project','id':project['id']},
            'code': seq_name,
            'sg_episode': episode,
            'description': 'SQ blah',
            }

        else:
            data = {
            'project': {'type':'Project','id':project['id']},
            'code': seq_name,
            'description': 'SQ blah',
            }

        seq = sg.create("Sequence", data)
        return seq #get new sequence

    def create_shot(self, project, shot_name, seq):
        data = {
        'project': {'type':'Project','id':project['id']},
        'code': shot_name,
        'sg_sequence': {'type':'Sequence','id':seq['id']},
        }

        shot = sg.create("Shot", data)
        return shot #get new shot

    def get_latest_version(self, item):
        #SHOT
        if item['type']== "Shot":
            #latest version = latest date and largest id number
            summaries = sg.summarize(entity_type='Version', filters=[
                ['project', 'is', {'type':'Project', 'id':item['proj_id']}],
                ['entity', 'is', {'type':'Shot', 'id':item['shot_id']}] ],
                summary_fields=[{'field':'created_at', 'type':'latest'},
                    {'field':'id', 'type':'maximum'}])

            if summaries['summaries']['id']!=0:

                fields = ['code']
                filters = [
                    ['project','is',{'type':'Project','id':item['proj_id']}],
                    ['id','is',summaries['summaries']['id']] ]

                last_version_number= sg.find_one("Version",filters,fields)['code'][-3:] #finding latest version number
                return int(last_version_number)

            else:
                return 1

        #VERSION
        else:
            return 0

    def ProjActivated(self):
        #when new project is selected everything else should be cleared
        self.selectEpi.clear()
        self.selectEpi.addItem(self.defaultEpisode)
        self.selectEpi.addItem("No Episode")
        self.selectSeq.clear()
        self.multiSelectDropDrown.clearItems()

        projName = self.getProjectName()
        if projName == self.defaultProject:
            return

        self.paths.project = projName
        for ep in self.paths.episodes:
            self.selectEpi.addItem(ep)

    def EpiActivated(self, text): #Epi DD triggered
        self.selectSeq.clear()
        self.multiSelectDropDrown.clearItems()
        epName = self.getEpName()
        if epName == self.defaultEpisode:
            return
        self.paths.episode = epName
        self.selectSeq.addItem(self.defaultSequence)
        for seq in self.paths.sequences:
            self.selectSeq.addItem(seq)

    def SeqActivated(self, text): #Seq DD triggered
        self.multiSelectDropDrown.clearItems()
        seqName = self.getSeqName()
        if seqName == self.defaultSequence:
            return

        self.paths.sequence = self.getSeqName()
        self.multiSelectDropDrown.addItems(["All"], selected=[])
        for shot in self.paths.shots:
            self.multiSelectDropDrown.addItems([shot], selected=[])

    def AddShotActivated(self):
        if not (self.animatic_check.isChecked() or self.shot_check.isChecked()
                or self.comp_check.isChecked() ):
            QMessageBox.question(self, 'Warning',
                    '''Please select a Shot or Animatic''', QMessageBox.Ok)

        if not self.check_input():
            return
        if not self.table:
            self.table = Table(self)
        self.table.show()

        shots = self.getSelectedShotNames()

        for shot in shots:
            self.paths.shot = shot

            if self.animatic_check.isChecked():
                clip_type = 'Animatic'
                clip_path = self.paths.animaticPath
            elif self.shot_check.isChecked():
                clip_type = 'Animation'
                clip_path = self.paths.animationPath
            elif self.comp_check.isChecked():
                clip_type = 'Comp'
                clip_path = self.paths.compPath

            self.table.setData( self.getProjectName(),
                    self.getEpName(),
                    self.getEpName() + "_"+ self.getSeqName(),
                    self.getEpName() + "_" + shot, clip_type, "")
            if not os.path.exists(clip_path):
                self.table.MyTable.setItem(self.table.MyTable.rowCount()-1
                        , 5, QTableWidgetItem("File not found"))
                self.table.setColour(self.table.MyTable.rowCount()-1,
                        "red")
            QApplication.processEvents()

    def check_input(self): #validating correct input
        if ( self.getProjectName() == self.defaultProject and
                self.getEpName() == self.defaultEpisode and
                self.getSeqName() == self.defaultSequence):
            return False
        return True

Form2, Base2=uic.loadUiType(osp.join(uiPath, 'table.ui'))
class Table(Form2, Base2):
    def __init__(self, parent=None):

        super(Table, self).__init__()
        self.setupUi(self)
        self.delete_button.clicked.connect(self.delete)
        self.upload_button.clicked.connect(self.upload)

        self.parentWin = parent
        self.workThread = WorkThread(self.parentWin)

        self.label.setText(user)
        self.refresh_button.clicked.connect(self.refresh_clicked)
        self.clear_button.clicked.connect(self.clear_all)



    def setData(self, p_name, e_name, seq_name, sh_name, sh_file, comments):

        rowPosition = self.MyTable.rowCount()
        self.MyTable.insertRow(rowPosition)
        self.MyTable.setItem(rowPosition , 0, QTableWidgetItem(p_name))
        self.MyTable.setItem(rowPosition , 1, QTableWidgetItem(e_name))
        self.MyTable.setItem(rowPosition , 2, QTableWidgetItem(seq_name))
        self.MyTable.setItem(rowPosition , 3, QTableWidgetItem(sh_name))
        self.MyTable.setItem(rowPosition , 4, QTableWidgetItem(sh_file))
        self.MyTable.setItem(rowPosition , 5, QTableWidgetItem(comments))

    def refresh_clicked(self):
        print "refresh"
        rows= self.MyTable.rowCount()
        for i in range (0, rows): #iterating each table row to check if file exists

            project_name= self.MyTable.item(i, 0).text()
            episode_name= self.MyTable.item(i, 1).text()
            seq_name= self.MyTable.item(i, 2).text()
            shot_name= self.MyTable.item(i, 3).text()
            shot_type= self.MyTable.item(i, 4).text()

            if shot_type=="Shot":
                shot_filename= shot_name[5:] + ".mov"
                print "File_name", shot_filename
                f_path=osp.join(self.parentWin.getInitialPath(project_name), episode_name, "SEQUENCES", seq_name[-5:], "SHOTS", shot_name[5:], "animation", "preview", shot_filename) #shot path
                print "FPATH", f_path

                if os.path.exists(f_path):
                        self.MyTable.setItem(i , 5, QTableWidgetItem(""))
                        self.setColour(i, "white")
                        QApplication.processEvents()
                else:
                    self.MyTable.setItem(i , 5, QTableWidgetItem("File not found"))
                    self.setColour(i, "red")
                    QApplication.processEvents()


            if shot_type=='Animatic': #animatic details
                animatic_filename= shot_name + "_animatic.mov"
                print "a_name", animatic_filename
                print seq_name
                a_path= osp.join(self.parentWin.getInitialPath(project_name), episode_name, "SEQUENCES", seq_name[-5:], "SHOTS", shot_name[5:], "animatic", animatic_filename) #animatic path
                print "a_path", a_path

                if os.path.exists(a_path):
                        self.MyTable.setItem(i , 5, QTableWidgetItem(""))
                        self.setColour(i, "white")

                else:
                    self.MyTable.setItem(i , 5, QTableWidgetItem("File not found"))
                    self.setColour(i, "red")
                    QApplication.processEvents()


    def setColour(self, rowPos, mycolour):
        if mycolour=="red":
            for i in range(0, 6):
                self.MyTable.item(rowPos, i).setBackground(Qt.red)

        if mycolour=="green":
            for i in range(0, 6):
                self.MyTable.item(rowPos, i).setBackground(Qt.green)

        if mycolour=="white":
            for i in range(0, 6):
                self.MyTable.item(rowPos, i).setBackground(Qt.white)

    def delete(self):
        current_row= self.MyTable.currentRow()
        self.MyTable.removeRow(current_row)

    def upload(self):
        self.workThread.start()

    def closeEvent(self, event):
        self.clear_all()

    def clear_all(self):
        self.MyTable.setRowCount(0)
        self.progress_label.setText("")
        self.parentWin.data_list= []
        self.parentWin.versions=[]

class WorkThread(QtCore.QThread):
    def __init__(self, p):
        QtCore.QThread.__init__(self)
        self.parentWin = p

    def __del__(self):
        self.wait()

    def run(self):
        self.parentWin.process_user_input()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.setWindowTitle("Select your file")
    win.show()
    sys.exit(app.exec_())
