'''
Created on Jul 11, 2015

@author: iqra.idrees
'''
import sip
from __builtin__ import True
#from wsgiref.validate import check_input
sip.setapi('QString', 2)
from PyQt4.QtGui import QApplication, QTableWidgetItem, QMessageBox
from PyQt4 import uic, QtCore
from PyQt4.QtCore import Qt, pyqtSignal
import sys
import os
from shotgun_api3 import Shotgun
import os.path as osp
import hashlib
import getpass
import re
import time

sys.path.insert(0, "R:\\Pipe_Repo\\Users\\Iqra\\modules")
sys.path.append("R:\\Pipe_Repo\\Users\\Qurban\\utilities")
import cui
import msgBox

SERVER_PATH = 'https://iceanimations.shotgunstudio.com'
SCRIPT_NAME = 'TestScript'
SCRIPT_KEY = '446a726a387c5f8372b1b6e6d30e4cd05d022475b51ea82ebe1cff34896cf2f2'
PROXY= None

sg= Shotgun(SERVER_PATH, SCRIPT_NAME, SCRIPT_KEY, http_proxy=PROXY)
user= getpass.getuser()
artist= sg.find_one("HumanUser", [['name', 'is', "ICE Animations"]], ['name'])

rootPath = osp.dirname(osp.dirname(__file__))
filePath= osp.join(rootPath, 'files\project_file.txt')
uiPath = osp.join(rootPath, 'ui')

class PathResolver(object):
    ''' All the local paths are resolved in this class '''
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
        self.table = UploadQueueTable(self)
        self.table.setWindowTitle("Upload Queue")
        self.thread= ProcessThread(self) #upload thread
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
            self.table = UploadQueueTable(self)
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
class UploadQueueTable(Form2, Base2):
    '''The upload queue manager '''
    progressUpdate = pyqtSignal(str)
    tableItemStatusUpdate = pyqtSignal(int, str, str)

    class RowStatus:
        kWaiting = 0
        kFailed = 1
        kBusy = 2
        kDone = 3

    def __init__(self, parent=None):
        super(UploadQueueTable, self).__init__()
        self.setupUi(self)
        self.stop_button.clicked.connect(self.stop)
        self.upload_button.clicked.connect(self.upload)

        self.parentWin = parent
        self.workThreads = []

        self.label.setText(user)
        self.refresh_button.clicked.connect(self.refresh_clicked)
        self.clear_button.clicked.connect(self.clear_all)
        self.delete_button.clicked.connect(self.delete)

        self.itemStatus = []
        self._mutex = QtCore.QMutex()
        self._mainThreadId = QtCore.QThread.currentThreadId()

        self._stop = False

        self.progressUpdate.connect(self.updateProgressLabel)
        self.tableItemStatusUpdate.connect(self.updateTableItemStatus)

    def isMainThread(self):
        return QtCore.QThread.currentThreadId() == self._mainThreadId

    def processEvents(self):
        if self.isMainThread():
            QApplication.processEvents()

    def updateProgressLabel(self, text):
        self.progress_label.setText(text)

    def updateTableItemStatus(self, idx, msg, colour):
        self.MyTable.setItem(idx, 5, QTableWidgetItem(msg))
        if colour:
            self.setColour(idx, colour)

    def setData(self, p_name, e_name, seq_name, sh_name, sh_file, comments):
        rowPosition = self.MyTable.rowCount()
        self.MyTable.insertRow(rowPosition)
        self.MyTable.setItem(rowPosition , 0, QTableWidgetItem(p_name))
        self.MyTable.setItem(rowPosition , 1, QTableWidgetItem(e_name))
        self.MyTable.setItem(rowPosition , 2, QTableWidgetItem(seq_name))
        self.MyTable.setItem(rowPosition , 3, QTableWidgetItem(sh_name))
        self.MyTable.setItem(rowPosition , 4, QTableWidgetItem(sh_file))
        self.MyTable.setItem(rowPosition , 5, QTableWidgetItem(comments))
        self._mutex.lock()
        self.itemStatus.append(self.RowStatus.kWaiting)
        self._mutex.unlock()

    def getNextRow(self):
        if self._stop:
            return -1, []
        for rowIndex in range( self.MyTable.rowCount() ):
            if ( self.itemStatus[rowIndex] == self.RowStatus.kWaiting):
                return rowIndex, [self.MyTable.item(rowIndex, c).text() for c in
                        range(6)]
        for rowIndex in range( self.MyTable.rowCount() ):
            if ( self.itemStatus[rowIndex] == self.RowStatus.kFailed ):
                return rowIndex, [self.MyTable.item(rowIndex, c).text() for c in
                        range(6)]
        return -1, []

    def progress(self):
        nRows = self.MyTable.rowCount()
        return len( [ True for rowIndex in range(nRows) if
            self.itemStatus[rowIndex] == self.RowStatus.kDone ] ), nRows

    def process_queue(self):
        conn = Shotgun(SERVER_PATH, SCRIPT_NAME, SCRIPT_KEY, http_proxy=PROXY)

        while 1:
            if self._stop:
                break
            self._mutex.lock()
            index, data = self.getNextRow()
            if not data:
                self._mutex.unlock()
                time.sleep(1)
            else:
                self.itemStatus[index] = self.RowStatus.kBusy
                self._mutex.unlock()
                self.tableItemStatusUpdate.emit(index, 'Processing ... ',
                        'yellow')
                self.processEvents()
                if self.process_row(index, data, conn):
                    self.itemStatus[index] = self.RowStatus.kDone
                else:
                    self.itemStatus[index] = self.RowStatus.kFailed
                self.progressUpdate.emit('%d of %d Completed! ... '%self.progress())

    def process_row(self, idx, data, conn=None):
        if conn is None:
            conn = sg

        project_name = data[0]
        episode_name = data[1]
        seq_name = data[2]
        shot_name = data[3]
        shot_type = data[4]

        paths = self.paths(idx)
        version_code_postfix = ''

        if shot_type == "Animation":
            version_code_postfix = '_'.join(['animation', 'preview'])
            file_path = paths.animationPath

        elif shot_type == 'Animatic':
            version_code_postfix = 'animatic'
            file_path = paths.animaticPath

        elif shot_type == 'Comp':
            version_code_postfix = '_'.join(['comp', 'preview'])
            file_path = paths.compPath

        if not os.path.exists(file_path):
            self.tableItemStatusUpdate.emit(idx, 'File Not Found', 'red')
            return False

        self.tableItemStatusUpdate.emit(idx, 'Linking ...', 'yellow')
        project = conn.find_one("Project",[['name','is',project_name]],['id', 'name'])

        #EPI DETAILS
        if episode_name!="No Episode":
            episode = conn.find_one("CustomEntity01",[['code','is',episode_name], ['project', 'is', project]],['id', 'code'])
            if not episode:
                episode=self.create_episode(project, episode_name)
        else:
            episode= []

        #SEQ DETAILS
        seq = conn.find_one("Sequence",[['code','is',seq_name],['project', 'is', project]],['id', 'code'])
        if not seq:
            seq= self.create_sequence(project, episode, seq_name)

        #SHOT DETAILS
        shot = conn.find_one("Shot",[['code','is',shot_name], ['project', 'is', project], ['sg_sequence', 'is', seq]],['id', 'code'])
        if not shot:
            shot=self.create_shot(project, shot_name, seq) #create new shot

        version = None

        version_filters = []
        version_filters.append(('project', 'is', project))
        version_filters.append(('entity', 'is', shot))
        version_filters.append(('code', 'contains',
            version_code_postfix))

        file_hash = create_hash(file_path)
        all_versions = conn.find('Version', version_filters, ['code',
            'sg_hash', 'created_at'])

        already_uploaded, max_version, version_number = False, None, 1

        if all_versions:
            already_uploaded = any([ver['sg_hash']==file_hash for ver
                in all_versions])
            max_version = max(all_versions, key=self.get_version_number)

        if max_version:
            version_number = self.get_version_number(max_version) + 1

        if version_number <= 0:
            version_number = 1
        version_string = 'V%03d'%version_number 

        if already_uploaded:
            self.tableItemStatusUpdate.emit(idx, 'Version already exists!', 'green')
            QApplication.processEvents()
            return True

        version_data = {
            'project': {'type':'Project', 'id':project['id']},
            'code': '_'.join([shot['code'], version_code_postfix, version_string]),
            'entity': {'type':'Shot', 'id': shot['id']},
            'user': artist,
            'created_by': artist
        }

        try:
            self.tableItemStatusUpdate.emit(idx, 'Uploading ...', 'yellow')
            QApplication.processEvents()
            version = conn.create('Version', data=version_data)
            conn.upload('Version', version['id'], file_path, 'sg_uploaded_movie')
            sg.update("Version", version['id'], {'sg_hash': file_hash} )
            self.tableItemStatusUpdate.emit(idx, 'Uploaded!', 'green')
            self.processEvents()
        except Exception as e:
            self.tableItemStatusUpdate.emit(idx, 'Error: %s'%str(e), 'red')
            self.processEvents()
            if version:
                conn.delete('Version', version['id'])
            self.itemStatus[idx] = self.RowStatus.kFailed
            return False

        return True

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

    def create_episode(self, project, episode_name, conn=None):

        if conn is None:
            conn = sg

        data = {
        'project': {'type':'Project','id':project['id']},
        'code': episode_name,
        'description': 'EP blah',
        }

        epi = conn.create("CustomEntity01", data)
        return epi #get epi id of the new episode

    def create_sequence(self, project, episode, seq_name, conn=None):
        if conn is None:
            conn = sg

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

        seq = conn.create("Sequence", data)
        return seq #get new sequence

    def create_shot(self, project, shot_name, seq, conn=None):
        if conn is None:
            conn = sg

        data = {
        'project': {'type':'Project','id':project['id']},
        'code': shot_name,
        'sg_sequence': {'type':'Sequence','id':seq['id']},
        }
        shot = conn.create("Shot", data)
        return shot

    def refresh_clicked(self):
        nrows = self.MyTable.rowCount()

        for rowIndex in range(nrows):
            status = self.itemStatus[rowIndex]
            if status == self.RowStatus.kFailed:
                paths = self.paths(rowIndex)
                shot_type = self.MyTable.item(rowIndex, 4).text()
                if shot_type == "Animation":
                    file_path = paths.animationPath
                elif shot_type == 'Animatic':
                    file_path = paths.animaticPath
                elif shot_type == 'Comp':
                    file_path = paths.compPath
                if os.path.exists(file_path):
                    self.itemStatus[rowIndex] = self.RowStatus.kWaiting
                    self.tableItemStatusUpdate.emit(rowIndex, '', 'white')
                    self.processEvents()

        return True

    def setColour(self, rowPos, mycolour):
        if mycolour=='red':
            mycolour = Qt.red
        elif mycolour=='green':
            mycolour = Qt.green
        elif mycolour=='blue':
            mycolour = Qt.blue
        elif mycolour=='yellow':
            mycolour = Qt.yellow
        else:
            mycolour = Qt.white
        self.MyTable.item(rowPos, 5).setBackground(mycolour)
        self.processEvents()

    def stop(self):
        self._stop = True
        self.progressUpdate.emit('Stopping Upload ...')
        self.processEvents()

        result = cui.showMessage(self, title='Stop Upload',
                msg = 'Process interrupted by user',
                ques = 'Do you want to terminate on going uploads immediately?',
                icon = QMessageBox.Question,
                btns=QMessageBox.Yes | QMessageBox.No)
        if result == QMessageBox.Yes:
            for thread in self.workThreads:
                try:
                    thread.terminate()
                except:
                    pass
            self.workThreads = []
        for idx in range( self.MyTable.rowCount() ):
            if self.itemStatus[idx] == self.RowStatus.kBusy:
                self.itemStatus[idx] = self.RowStatus.kFailed
                self.tableItemStatusUpdate.emit(idx, 'Stopped', 'red')
        self.upload_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.clear_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.processEvents()
        self.progressUpdate.emit('Upload Stopped!')

    def upload(self):
        self._stop = False
        self.upload_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        if not self.workThreads:
            for i in range(4):
                self.workThreads.append( ProcessThread(self) )
        self.progressUpdate.emit('Processing Items ... ')
        self.stop_button.setEnabled(True)
        self.processEvents()
        for thread in self.workThreads:
            thread.start()

    def closeEvent(self, event):
        self.stop()
        self.clear_all()
        self.hide()
        event.ignore()

    def clear_all(self):
        self.MyTable.setRowCount(0)
        self.progress_label.setText("")
        self.parentWin.data_list= []
        self.parentWin.versions=[]

    def delete(self):
        self._mutex.lock()
        rowIndex = self.MyTable.currentRow()
        self.MyTable.removeRow(rowIndex)
        self.itemStatus = ( self.itemStatus[:rowIndex] +
                self.itemStatus[rowIndex+1:] )
        self._mutex.unlock()

    def paths(self, i):
        project_name= self.MyTable.item(i, 0).text()
        episode_name= self.MyTable.item(i, 1).text()
        seq_name= self.MyTable.item(i, 2).text()
        shot_name= self.MyTable.item(i, 3).text()
        return PathResolver(project_name, episode_name,
                '_'.join( seq_name.split('_')[1:] ),
                '_'.join( shot_name.split('_')[1:] ))

class ProcessThread(QtCore.QThread):
    def __init__(self, p):
        QtCore.QThread.__init__(self, parent=p)
        self.parentWin = p

    def __del__(self):
        self.wait()

    def run(self):
        self.parentWin.process_queue()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.setWindowTitle("Select your file")
    win.show()
    sys.exit(app.exec_())

