try:
    from uiContainer import uic
except:
    from PyQt4 import uic
from PyQt4.QtGui import *
import os.path as osp

rootPath = osp.dirname(__file__)
uiPath = osp.join(rootPath, 'ci_ui')

Form2, Base2 = uic.loadUiType(osp.join(uiPath, 'selectionBox.ui'))
class SelectionBox(Form2, Base2):
    def __init__(self, parent=None, items=None, msg=''):
        '''
        @param items: objects of QCheckbox or QRadioButton
        '''
        super(SelectionBox, self).__init__(parent)
        self.setupUi(self)
        
        self.setMessage(msg)
        self.okButton.clicked.connect(self.ok)
        
        self.selectedItems = []
        self.items = items
        for item in items:
            self.itemsLayout.addWidget(item)
            
    def setCancelToolTip(self, tip):
        self.cancelButton.setToolTip(tip)
        
    def setMessage(self, msg):
        self.msgLabel.setText(msg)
        
    def ok(self):
        if not [item for item in self.items if item.isChecked()]:
            showMessage(self, title='Items Selection',
                        msg='Please select at least one item',
                        icon=QMessageBox.Information)
            return
        self.selectedItems = [item.text() for item in self.items if item.isChecked()]
        self.accept()
        
    def getSelectedItems(self):
        return self.selectedItems

Form1, Base1 = uic.loadUiType(osp.join(uiPath, 'multiSelectComboBox.ui'))
class MultiSelectComboBox(Form1, Base1):
    def __init__(self, parent=None, msg='--Select Shots--'):
        super(MultiSelectComboBox, self).__init__(parent)
        self.setupUi(self)
        
        self.msg = msg
        self.menu = QMenu(self)
        self.menu.setStyleSheet("QMenu { menu-scrollable: 1; }")
        self.button.setMenu(self.menu)
        
        self.menu.hideEvent = self.menuHideEvent
        self.setHintText(self.msg)
        
    def setHintText(self, text):
        self.button.setText(text)
        
    def menuHideEvent(self, event):
        items = self.getSelectedItems()
        if items:
            s = ''
            if len(items) > 2:
                s = ',...'
            self.button.setText(','.join(items[:2]) + s)
        else:
            self.setHintText(self.msg)
        if event:
            QMenu.hideEvent(self.menu, event)
        
    def getSelectedItems(self):
        return [cBox.text().strip() for cBox in
                [action.defaultWidget() for action in
                 self.menu.actions()] if cBox.isChecked()]
        
    def getItems(self):
        return [cBox.text().strip() for cBox in
                [action.defaultWidget() for action in
                 self.menu.actions()]]

    def addItems(self, items, selected=None):
        items = sorted(items)
        #self.clearItems()
        for item in items:
            checkBox = QCheckBox(item, self.menu)
            if selected and item in selected:
                checkBox.setChecked(True)
            checkableAction = QWidgetAction(self.menu)
            checkableAction.setDefaultWidget(checkBox)
            self.menu.addAction(checkableAction)
        if selected:
            self.menuHideEvent(None)

    def clearItems(self):
        self.menu.clear()
        self.setHintText(self.msg)

class MessageBox(QMessageBox):
    def __init__(self, parent=None):
        super(MessageBox, self).__init__(parent)

    def closeEvent(self, event):
        self.deleteLater()

def showMessage(parent, title = 'Shot Export',
                msg = 'Message', btns = QMessageBox.Ok,
                icon = None, ques = None, details = None, **kwargs):

    mBox = MessageBox(parent)
    mBox.setWindowTitle(title)
    mBox.setText(msg)
    if ques:
        mBox.setInformativeText(ques)
    if icon:
        mBox.setIcon(icon)
    if details:
        mBox.setDetailedText(details)
    customButtons = kwargs.get('customButtons')
    mBox.setStandardButtons(btns)
    if customButtons:
        for btn in customButtons:
            mBox.addButton(btn, QMessageBox.AcceptRole)
    pressed = mBox.exec_()
    if customButtons:
        cBtn = mBox.clickedButton()
        if cBtn in customButtons:
            return cBtn
    return pressed
